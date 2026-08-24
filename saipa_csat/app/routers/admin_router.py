from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_admin, hash_password

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db), user=Depends(require_admin)):
    users = db.execute(select(models.User).order_by(models.User.created_at)).scalars().all()
    return templates.TemplateResponse("admin_users.html", {"request": request, "user": user, "users": users})


@router.post("/users")
def create_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("staff"),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    existing = db.execute(select(models.User).where(models.User.username == username)).scalars().first()
    if not existing:
        db.add(models.User(
            username=username, full_name=full_name, password_hash=hash_password(password), role=role,
        ))
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    target = db.get(models.User, user_id)
    if target and target.id != user.id:
        target.is_active = not target.is_active
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)
