from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .database import get_db
from . import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_KEY = "user_id"


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def login_user(request: Request, user: models.User) -> None:
    request.session[SESSION_KEY] = user.id


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return None
    user = db.get(models.User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = require_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="دسترسی محدود به مدیر سیستم است")
    return user
