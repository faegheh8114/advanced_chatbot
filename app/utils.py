import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import ActivityLog, Notification


def log_activity(actor, action, description, target_type=None, target_id=None):
    entry = ActivityLog(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
    )
    db.session.add(entry)
    return entry


def notify(user, type_, title, body=None, ticket=None):
    if user is None:
        return None
    notification = Notification(
        user_id=user.id,
        type=type_,
        title=title,
        body=body,
        ticket_id=ticket.id if ticket else None,
    )
    db.session.add(notification)
    return notification


def notify_many(users, type_, title, body=None, ticket=None, exclude_user_id=None):
    seen = set()
    for user in users:
        if user is None or user.id in seen or user.id == exclude_user_id:
            continue
        seen.add(user.id)
        notify(user, type_, title, body=body, ticket=ticket)


def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


def save_upload(file_storage, subfolder):
    """Validates and saves an uploaded file. Returns (stored_filename, original_filename, size) or raises ValueError."""
    original_name = secure_filename(file_storage.filename or "")
    if not original_name:
        raise ValueError("Invalid file name.")
    if not allowed_file(original_name):
        raise ValueError(f"File type not allowed: {original_name}")

    ext = original_name.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"

    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, stored_name)

    file_storage.save(target_path)
    size = os.path.getsize(target_path)
    return stored_name, original_name, size


def humanize_dt(dt):
    if dt is None:
        return ""
    from datetime import datetime

    delta = datetime.utcnow() - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h ago"
    days = int(seconds // 86400)
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d, %Y")
