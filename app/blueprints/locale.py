from flask import Blueprint, redirect, request, session
from flask_login import current_user

from app.extensions import db
from app.translations import SUPPORTED_LOCALES

locale_bp = Blueprint("locale", __name__)


@locale_bp.route("/set-language/<lang>", methods=["POST"])
def set_language(lang):
    if lang in SUPPORTED_LOCALES:
        session["lang"] = lang
        if current_user.is_authenticated:
            current_user.language = lang
            db.session.commit()
    return redirect(request.referrer or "/")
