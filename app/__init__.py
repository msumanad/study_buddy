from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.config import BASE_DIR


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "info"


def create_app():
    # Point Flask to the project's top-level templates and static folders
    templates_dir = str(BASE_DIR / "templates")
    static_dir = str(BASE_DIR / "static")
    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir, static_url_path="/static")
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app.models import User
        db.create_all()
        from app.routes import register_routes
        register_routes(app)
        seed_default_users()

    return app


def seed_default_users():
    from app.models import User

    admin = User.query.filter_by(username="admin").first()
    if not admin:
        User.create_user("admin", "admin123", "admin")

    normal_user = User.query.filter_by(username="user").first()
    if not normal_user:
        User.create_user("user", "user123", "user")
