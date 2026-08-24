import os

from flask import Flask

from app.config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.tickets import tickets_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.notifications import notifications_bp
    from app.blueprints.profile import profile_bp
    from app.blueprints.api import api_bp
    from app.blueprints.locale import locale_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(locale_bp)

    from app.template_helpers import register_template_helpers

    register_template_helpers(app)

    from app.errors import register_error_handlers

    register_error_handlers(app)

    return app
