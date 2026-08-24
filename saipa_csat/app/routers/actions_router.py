import datetime as dt

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user
from ..analytics import action_effectiveness
from ..corrective_actions import generate_suggestions

router = APIRouter(prefix="/actions")
templates = Jinja2Templates(directory="app/templates")

STATUSES = ["در حال بررسی", "در حال اجرا", "تکمیل شده", "لغو شده"]


@router.get("")
def list_actions(request: Request, status: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    query = select(models.CorrectiveAction).order_by(models.CorrectiveAction.created_at.desc())
    if status:
        query = query.where(models.CorrectiveAction.status == status)
    actions = db.execute(query).scalars().all()
    enriched = [{"action": a, "effect": action_effectiveness(a)} for a in actions]
    suggestions = generate_suggestions(db, top_n=3)
    return templates.TemplateResponse(
        "actions_list.html",
        {"request": request, "items": enriched, "suggestions": suggestions, "statuses": STATUSES,
         "status_filter": status, "user": user},
    )


@router.get("/new")
def new_action_form(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    prefill = dict(request.query_params)
    return templates.TemplateResponse("action_form.html", {"request": request, "user": user, "prefill": prefill})


@router.post("/new")
def create_action(
    request: Request,
    title: str = Form(...),
    problem: str = Form(...),
    evidence: str = Form(...),
    root_cause: str = Form(...),
    action: str = Form(...),
    owner: str = Form(...),
    deadline: str = Form(""),
    kpi_name: str = Form(...),
    baseline_value: str = Form(""),
    target_value: str = Form(""),
    related_question_code: str = Form(""),
    related_reason: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_user),
):
    ca = models.CorrectiveAction(
        title=title, problem=problem, evidence=evidence, root_cause=root_cause, action=action,
        owner=owner, deadline=dt.date.fromisoformat(deadline) if deadline else None,
        kpi_name=kpi_name,
        baseline_value=float(baseline_value) if baseline_value else None,
        target_value=float(target_value) if target_value else None,
        related_question_code=related_question_code or None,
        related_reason=related_reason or None,
        created_by=user.id, updated_by=user.id,
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)

    if ca.baseline_value is not None:
        db.add(models.ActionFollowUp(
            action_id=ca.id, measured_date=dt.date.today(), measured_value=ca.baseline_value,
            note="مقدار پایه (قبل از اجرای اقدام)", created_by=user.id,
        ))
        db.commit()

    return RedirectResponse(f"/actions/{ca.id}", status_code=303)


@router.get("/{action_id}")
def action_detail(action_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    ca = db.get(models.CorrectiveAction, action_id)
    effect = action_effectiveness(ca)
    return templates.TemplateResponse(
        "action_detail.html",
        {"request": request, "a": ca, "effect": effect, "statuses": STATUSES, "user": user, "today": dt.date.today().isoformat()},
    )


@router.post("/{action_id}/status")
def update_status(action_id: int, status: str = Form(...), db: Session = Depends(get_db), user=Depends(require_user)):
    ca = db.get(models.CorrectiveAction, action_id)
    ca.status = status
    ca.updated_by = user.id
    db.commit()
    return RedirectResponse(f"/actions/{action_id}", status_code=303)


@router.post("/{action_id}/measure")
def add_measurement(
    action_id: int, measured_date: str = Form(...), measured_value: float = Form(...), note: str = Form(""),
    db: Session = Depends(get_db), user=Depends(require_user),
):
    db.add(models.ActionFollowUp(
        action_id=action_id, measured_date=dt.date.fromisoformat(measured_date),
        measured_value=measured_value, note=note or None, created_by=user.id,
    ))
    db.commit()
    return RedirectResponse(f"/actions/{action_id}", status_code=303)
