from flask import request, url_for
from flask_login import current_user

from app.config import Config
from app.models import Role, TicketStatus, TicketPriority
from app.utils import humanize_dt


def register_template_helpers(app):
    @app.template_global()
    def url_for_page(page):
        args = request.args.to_dict(flat=True)
        args["page"] = page
        return url_for(request.endpoint, **args, **request.view_args)

    @app.context_processor
    def inject_globals():
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = current_user.unread_notification_count()
        return {
            "ORG_NAME": Config.ORG_NAME,
            "ORG_CODE": Config.ORG_CODE,
            "ORG_FULL_NAME": Config.ORG_FULL_NAME,
            "Role": Role,
            "TicketStatus": TicketStatus,
            "TicketPriority": TicketPriority,
            "unread_notification_count": unread_count,
        }

    app.jinja_env.filters["timeago"] = humanize_dt
