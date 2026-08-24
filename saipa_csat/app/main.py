import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine, SessionLocal
from . import seed
from .routers import (
    auth_router, customers, survey_router, followup_router, actions_router,
    comparison_router, import_router, export_router, dashboard_router, reports_router, admin_router,
)

app = FastAPI(title="سامانه رضایت مشتری - سایپا مشایخ ۳۲۹۹")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("CSAT_SECRET_KEY", "dev-secret-change-me-in-production"),
    session_cookie="csat_session",
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(customers.router)
app.include_router(survey_router.router)
app.include_router(followup_router.router)
app.include_router(actions_router.router)
app.include_router(comparison_router.router)
app.include_router(import_router.router)
app.include_router(export_router.router)
app.include_router(reports_router.router)
app.include_router(admin_router.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed.run_seed(db)
    finally:
        db.close()
