from flask import request, session, url_for
from flask_login import current_user

from app.config import Config
from app.models import Role, TicketStatus, TicketPriority
from app.utils import humanize_dt
from app.translations import (
    TRANSLATIONS, STATUS_LABELS, PRIORITY_LABELS, ROLE_LABELS,
    DEFAULT_LOCALE, SUPPORTED_LOCALES,
)


def get_locale():
    # An explicit choice made in this browser session (e.g. on the login page,
    # or via the language switch) always wins, so a pre-login pick sticks
    # through sign-in. Otherwise fall back to the account's saved preference.
    lang = session.get("lang")
    if lang in SUPPORTED_LOCALES:
        return lang
    if current_user.is_authenticated and current_user.language in SUPPORTED_LOCALES:
        return current_user.language
    return DEFAULT_LOCALE


def register_template_helpers(app):
    @app.template_global()
    def url_for_page(page):
        args = request.args.to_dict(flat=True)
        args["page"] = page
        return url_for(request.endpoint, **args, **request.view_args)

    @app.template_global()
    def t(key, **kwargs):
        locale = get_locale()
        text = TRANSLATIONS.get(locale, {}).get(key) or TRANSLATIONS[DEFAULT_LOCALE].get(key) or key
        return text.format(**kwargs) if kwargs else text

    @app.template_global()
    def status_label(status):
        locale = get_locale()
        return STATUS_LABELS.get(locale, {}).get(status) or STATUS_LABELS[DEFAULT_LOCALE].get(status, status)

    @app.template_global()
    def priority_label(priority):
        locale = get_locale()
        return PRIORITY_LABELS.get(locale, {}).get(priority) or PRIORITY_LABELS[DEFAULT_LOCALE].get(priority, priority)

    @app.template_global()
    def role_label(role):
        locale = get_locale()
        return ROLE_LABELS.get(locale, {}).get(role) or ROLE_LABELS[DEFAULT_LOCALE].get(role, role)

    @app.context_processor
    def inject_globals():
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = current_user.unread_notification_count()
        locale = get_locale()
        return {
            "ORG_NAME": Config.ORG_NAME,
            "ORG_CODE": Config.ORG_CODE,
            "ORG_FULL_NAME": Config.ORG_FULL_NAME,
            "Role": Role,
            "TicketStatus": TicketStatus,
            "TicketPriority": TicketPriority,
            "unread_notification_count": unread_count,
            "CURRENT_LOCALE": locale,
            "IS_RTL": locale == "fa",
        }

    app.jinja_env.filters["timeago"] = humanize_dt
