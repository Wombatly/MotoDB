from datetime import datetime
import os
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix


db = SQLAlchemy()
csrf = CSRFProtect()

DEFAULT_SECRET_KEY = "dev-change-me"
DEFAULT_ADMIN_EMAIL = "admin@localhost"
DEFAULT_ADMIN_PASSWORD = "change-me-please"


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app():
    instance_path = os.environ.get("MOTORRAD_INSTANCE_PATH")
    app = Flask(__name__, instance_path=instance_path) if instance_path else Flask(__name__)
    public_hosting = env_bool("MOTODB_PUBLIC_HOSTING")
    secret_key = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)
    if public_hosting and secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "Setze SECRET_KEY auf einen langen zufaelligen Wert, bevor MOTODB_PUBLIC_HOSTING aktiv ist."
        )

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///motorcycle_service.sqlite3",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = Path(
        os.environ.get("MOTORRAD_UPLOAD_FOLDER", Path(app.instance_path) / "uploads")
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["MOTODB_PUBLIC_HOSTING"] = public_hosting
    app.config["MOTODB_ALLOW_REGISTRATION"] = env_bool(
        "MOTODB_ALLOW_REGISTRATION",
        default=not public_hosting,
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = public_hosting
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SECURE"] = public_hosting
    app.config["PREFERRED_URL_SCHEME"] = "https" if public_hosting else "http"

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)

    if env_bool("MOTODB_TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Bitte melde dich an.'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("Content-Security-Policy", security_policy())
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )
        if app.config["MOTODB_PUBLIC_HOSTING"]:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000",
            )
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return "Ungueltige oder abgelaufene Formularanfrage.", 400

    from app.routes import bp
    from app.auth import auth_bp

    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()
        ensure_admin(public_hosting)
        ensure_schema_updates()
        ensure_default_settings()

    return app


def security_policy():
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "connect-src 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "img-src 'self' data:",
            "object-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
        ]
    )


def ensure_schema_updates():
    with db.engine.connect() as connection:
        admin_id = connection.exec_driver_sql(
            "SELECT id FROM user WHERE is_admin = 1 ORDER BY id LIMIT 1"
        ).scalar()

        for table_name in ['motorcycle', 'service_entry', 'technical_spec', 'service_checklist']:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})")
            }
            if "user_id" not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER REFERENCES user(id)"
                )

            if admin_id is not None:
                connection.exec_driver_sql(
                    f"UPDATE {table_name} SET user_id = :admin_id WHERE user_id IS NULL",
                    {"admin_id": admin_id},
                )

        checklist_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(service_checklist)")
        }
        if "is_template" not in checklist_columns:
            connection.exec_driver_sql(
                "ALTER TABLE service_checklist ADD COLUMN is_template BOOLEAN NOT NULL DEFAULT 1"
            )
        if "source_template_id" not in checklist_columns:
            connection.exec_driver_sql(
                "ALTER TABLE service_checklist ADD COLUMN source_template_id INTEGER"
            )
        connection.exec_driver_sql(
            "UPDATE service_checklist SET is_template = 0 WHERE completed_at IS NOT NULL"
        )

        item_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(service_checklist_item)")
        }
        if "kommentar_vorlage" not in item_columns:
            connection.exec_driver_sql(
                "ALTER TABLE service_checklist_item ADD COLUMN kommentar_vorlage TEXT"
            )
        connection.commit()


def ensure_admin(public_hosting=False):
    from app.models import User
    from sqlalchemy.exc import IntegrityError

    admin_user = User.query.filter_by(is_admin=True).first()
    if admin_user:
        if public_hosting and admin_user.check_password(DEFAULT_ADMIN_PASSWORD):
            raise RuntimeError(
                "Aendere das bekannte Default-Admin-Passwort, bevor MOTODB_PUBLIC_HOSTING aktiv ist."
            )
        return

    admin_username = os.environ.get("MOTODB_ADMIN_USERNAME", "").strip()
    admin_email = os.environ.get("MOTODB_ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("MOTODB_ADMIN_PASSWORD", "")
    bootstrap_values = [admin_username, admin_email, admin_password]
    if any(bootstrap_values):
        if not all(bootstrap_values):
            raise RuntimeError(
                "Setze MOTODB_ADMIN_USERNAME, MOTODB_ADMIN_EMAIL und MOTODB_ADMIN_PASSWORD gemeinsam."
            )
        if len(admin_password) < 12:
            raise RuntimeError("MOTODB_ADMIN_PASSWORD muss mindestens 12 Zeichen lang sein.")

        existing_user = User.query.filter(
            db.or_(User.username == admin_username, User.email == admin_email)
        ).first()
        if existing_user:
            existing_user.is_admin = True
            existing_user.consent_accepted_at = existing_user.consent_accepted_at or datetime.utcnow()
            existing_user.set_password(admin_password)
            db.session.commit()
            return

        admin = User(
            username=admin_username,
            email=admin_email,
            is_admin=True,
            consent_accepted_at=datetime.utcnow(),
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        try:
            db.session.commit()
            print(f"Admin erstellt: {admin_email}")
        except IntegrityError:
            db.session.rollback()
        return

    if public_hosting:
        raise RuntimeError(
            "Lege den ersten Admin ueber MOTODB_ADMIN_USERNAME, MOTODB_ADMIN_EMAIL "
            "und MOTODB_ADMIN_PASSWORD an."
        )

    existing_user = User.query.filter(
        db.or_(User.username == "admin", User.email == DEFAULT_ADMIN_EMAIL)
    ).first()
    if existing_user:
        existing_user.is_admin = True
        existing_user.consent_accepted_at = existing_user.consent_accepted_at or datetime.utcnow()
        db.session.commit()
        return

    admin = User(
        username="admin",
        email=DEFAULT_ADMIN_EMAIL,
        is_admin=True,
        consent_accepted_at=datetime.utcnow(),
    )
    admin.set_password(DEFAULT_ADMIN_PASSWORD)
    db.session.add(admin)
    try:
        db.session.commit()
        print("WARNUNG: Default Admin erstellt: admin@localhost / change-me-please")
    except IntegrityError:
        db.session.rollback()


def ensure_default_settings():
    from app.models import AppSetting

    if not AppSetting.query.get("backup_path"):
        db.session.add(
            AppSetting(
                key="backup_path",
                value="/PFAD/ZUM/SICHERUNGSORDNER",
            )
        )
        db.session.commit()
