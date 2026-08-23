from functools import wraps

from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """Backend-enforced RBAC guard. 403s if the current user's role isn't allowed."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view_func):
    from app.models import Role

    return roles_required(Role.SUPER_ADMIN, Role.ADMIN)(view_func)


def super_admin_required(view_func):
    from app.models import Role

    return roles_required(Role.SUPER_ADMIN)(view_func)
