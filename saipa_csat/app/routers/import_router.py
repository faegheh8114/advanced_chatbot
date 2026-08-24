from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_admin
from .. import importer

router = APIRouter(prefix="/import")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def import_page(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse("import_upload.html", {"request": request, "user": user})


@router.post("")
async def upload_file(request: Request, file: UploadFile = File(...), user=Depends(require_admin)):
    content = await file.read()
    import_id = importer.save_upload(content)
    return RedirectResponse(f"/import/preview/{import_id}", status_code=303)


@router.get("/preview/{import_id}")
def preview(import_id: str, request: Request, user=Depends(require_admin)):
    df = importer.load_dataframe(import_id)
    mapping = importer.suggest_mapping(df)
    validation = importer.validate(df, mapping)
    return templates.TemplateResponse(
        "import_preview.html",
        {
            "request": request, "user": user, "import_id": import_id,
            "columns": list(df.columns), "mapping": mapping, "validation": validation,
            "preview_rows": df.head(10).to_dict("records"),
            "mappable_fields": importer.MAPPABLE_FIELDS,
        },
    )


@router.post("/preview/{import_id}")
async def revalidate(import_id: str, request: Request, user=Depends(require_admin)):
    form = await request.form()
    df = importer.load_dataframe(import_id)
    mapping = {col: form.get(f"map_{i}", "") for i, col in enumerate(df.columns)}
    validation = importer.validate(df, mapping)
    return templates.TemplateResponse(
        "import_preview.html",
        {
            "request": request, "user": user, "import_id": import_id,
            "columns": list(df.columns), "mapping": mapping, "validation": validation,
            "preview_rows": df.head(10).to_dict("records"),
            "mappable_fields": importer.MAPPABLE_FIELDS,
        },
    )


@router.post("/commit/{import_id}")
async def commit(import_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_admin)):
    form = await request.form()
    df = importer.load_dataframe(import_id)
    mapping = {col: form.get(f"map_{i}", "") for i, col in enumerate(df.columns)}
    validation = importer.validate(df, mapping)
    if not validation["can_commit"]:
        return RedirectResponse(f"/import/preview/{import_id}", status_code=303)

    dealership = db.execute(select(models.Dealership)).scalars().first()
    result = importer.commit_import(db, df, mapping, dealership.id, user.id)
    return templates.TemplateResponse(
        "import_result.html", {"request": request, "user": user, "result": result},
    )
