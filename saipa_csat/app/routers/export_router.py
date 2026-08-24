import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import require_user
from .. import importer

router = APIRouter(prefix="/export")

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _stream(data: bytes, filename: str):
    return StreamingResponse(
        io.BytesIO(data), media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/surveys")
def export_surveys(db: Session = Depends(get_db), user=Depends(require_user)):
    df = importer.surveys_dataframe(db, source="direct_call")
    data = importer.dataframe_to_xlsx_bytes({"تماس‌های مستقیم": df})
    return _stream(data, "surveys.xlsx")


@router.get("/followups")
def export_followups(db: Session = Depends(get_db), user=Depends(require_user)):
    df = importer.followups_dataframe(db)
    data = importer.dataframe_to_xlsx_bytes({"پیگیری‌ها": df})
    return _stream(data, "followups.xlsx")


@router.get("/actions")
def export_actions(db: Session = Depends(get_db), user=Depends(require_user)):
    df = importer.actions_dataframe(db)
    data = importer.dataframe_to_xlsx_bytes({"اقدامات اصلاحی": df})
    return _stream(data, "corrective_actions.xlsx")
