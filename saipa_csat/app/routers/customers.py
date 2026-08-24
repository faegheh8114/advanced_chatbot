from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from ..database import get_db
from .. import models
from ..auth import require_user

router = APIRouter(prefix="/customers")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_customers(request: Request, q: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    query = select(models.Customer).order_by(models.Customer.created_at.desc())
    if q:
        like = f"%{q}%"
        query = query.where(or_(models.Customer.full_name.ilike(like), models.Customer.phone.ilike(like)))
    customers = db.execute(query.limit(100)).scalars().all()
    return templates.TemplateResponse(
        "customers_list.html", {"request": request, "customers": customers, "q": q, "user": user}
    )


@router.get("/new")
def new_customer_form(request: Request, user=Depends(require_user)):
    return templates.TemplateResponse("customer_form.html", {"request": request, "user": user})


@router.post("/new")
def create_customer(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    vehicle_model: str = Form(""),
    vehicle_plate: str = Form(""),
    gender: str = Form(""),
    age: str = Form(""),
    education: str = Form(""),
    job: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_user),
):
    customer = models.Customer(
        full_name=full_name.strip(),
        phone=phone.strip(),
        vehicle_model=vehicle_model or None,
        vehicle_plate=vehicle_plate or None,
        gender=gender or None,
        age=int(age) if age.isdigit() else None,
        education=education or None,
        job=job or None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return RedirectResponse(f"/surveys/new?customer_id={customer.id}", status_code=303)


@router.get("/{customer_id}")
def customer_detail(customer_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    customer = db.get(models.Customer, customer_id)
    surveys = db.execute(
        select(models.Survey).where(models.Survey.customer_id == customer_id).order_by(models.Survey.survey_date.desc())
    ).scalars().all()
    return templates.TemplateResponse(
        "customer_detail.html", {"request": request, "customer": customer, "surveys": surveys, "user": user}
    )
