from contextlib import contextmanager
from app.timeutils import utcnow
import fcntl
import mimetypes
import os
from pathlib import Path

from flask import Flask, request
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from werkzeug.middleware.proxy_fix import ProxyFix


db = SQLAlchemy()
csrf = CSRFProtect()

# Schlanke Container-Images haben keine /etc/mime.types; ohne diese Eintraege
# wuerden die selbst gehosteten Fonts als application/octet-stream ausgeliefert.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("application/manifest+json", ".webmanifest")

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
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    app.config["MOTODB_PUBLIC_HOSTING"] = public_hosting
    app.config["MOTODB_ALLOW_REGISTRATION"] = env_bool(
        "MOTODB_ALLOW_REGISTRATION",
        default=not public_hosting,
    )
    app.config["MOTODB_CONTROLLER_NAME"] = os.environ.get(
        "MOTODB_CONTROLLER_NAME",
        "Betreiber dieser MotoDB-Installation",
    )
    app.config["MOTODB_CONTROLLER_CONTACT"] = os.environ.get(
        "MOTODB_CONTROLLER_CONTACT",
        "ueber den Administrator dieser Installation",
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

    app.config["MOTODB_TRUST_PROXY_HEADERS"] = env_bool("MOTODB_TRUST_PROXY_HEADERS")
    if app.config["MOTODB_TRUST_PROXY_HEADERS"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    else:
        app.logger.warning(
            "MOTODB_TRUST_PROXY_HEADERS ist aus. Hinter einem Reverse Proxy sehen alle "
            "Requests wie 127.0.0.1 aus; das IP-basierte Login-Rate-Limit wird dann "
            "deaktiviert und nur pro E-Mail limitiert."
        )

    db.init_app(app)
    csrf.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Bitte melde dich an.'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    app.add_template_global(uses_default_admin_password, "uses_default_admin_password")

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
        # Angemeldete Seiten nicht im Browser-/Back-Forward-Cache ablegen,
        # damit der Zurueck-Button keine zwischengespeicherte Seite zeigt.
        if current_user.is_authenticated and not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if app.config["MOTODB_PUBLIC_HOSTING"] and not request.is_secure:
            return (
                "Formularanfragen ueber HTTP sind im Public-Hosting-Modus blockiert. "
                "Oeffne die App ueber HTTPS oder deaktiviere "
                "MOTODB_PUBLIC_HOSTING fuer ein lokales HTTP-Deployment.",
                400,
            )
        return "Ungueltige oder abgelaufene Formularanfrage.", 400

    from app.routes import bp
    from app.auth import auth_bp

    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)

    with app.app_context(), startup_lock(app.instance_path):
        db.create_all()
        ensure_admin(public_hosting)
        ensure_schema_updates()
        ensure_default_settings()
        from app.routes import reconcile_all_motorcycle_mileages
        reconcile_all_motorcycle_mileages()

    return app


@contextmanager
def startup_lock(instance_path):
    """Serialisiert Schema-Anlage und Migrationen ueber Prozessgrenzen hinweg.

    Gunicorn startet mehrere Worker, die alle create_app() ausfuehren. Ohne
    Sperre koennen zwei Worker gleichzeitig "ALTER TABLE" auf dieselbe SQLite-
    Datei absetzen; der zweite scheitert dann mit "duplicate column".
    """
    lock_path = Path(instance_path) / ".motodb-startup.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


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
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS motorcycle_image (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                motorcycle_id INTEGER NOT NULL REFERENCES motorcycle(id),
                path VARCHAR(255) NOT NULL,
                original_name VARCHAR(255),
                position INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS motorcycle_document (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES user(id),
                motorrad_id INTEGER NOT NULL REFERENCES motorcycle(id),
                titel VARCHAR(160) NOT NULL,
                kategorie VARCHAR(80) NOT NULL,
                path VARCHAR(255) NOT NULL,
                original_name VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        admin_id = connection.exec_driver_sql(
            "SELECT id FROM user WHERE is_admin = 1 ORDER BY id LIMIT 1"
        ).scalar()

        for table_name in ['motorcycle', 'service_entry', 'technical_spec', 'service_checklist', 'motorcycle_document']:
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

        spec_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(technical_spec)")
        }
        if "position" not in spec_columns:
            connection.exec_driver_sql(
                "ALTER TABLE technical_spec ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
            )
            connection.exec_driver_sql(
                """
                UPDATE technical_spec
                SET position = (
                    SELECT COUNT(*)
                    FROM technical_spec AS earlier
                    WHERE earlier.motorrad_id = technical_spec.motorrad_id
                      AND (
                          COALESCE(earlier.kategorie, '') < COALESCE(technical_spec.kategorie, '')
                          OR (COALESCE(earlier.kategorie, '') = COALESCE(technical_spec.kategorie, '') AND earlier.name < technical_spec.name)
                          OR (COALESCE(earlier.kategorie, '') = COALESCE(technical_spec.kategorie, '') AND earlier.name = technical_spec.name AND earlier.id < technical_spec.id)
                      )
                )
                """
            )

        # Aufraeumen: AuditLog hatte nie eine Schreibstelle, "aktiv" nie ein
        # Formularfeld (immer true). Beides wurde 2026-09 entfernt.
        connection.exec_driver_sql("DROP TABLE IF EXISTS audit_log")
        motorcycle_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(motorcycle)")
        }
        if "aktiv" in motorcycle_columns:
            connection.exec_driver_sql("ALTER TABLE motorcycle DROP COLUMN aktiv")

        # Einmalige Bereinigung: fruehere Datenblatt-Autosaves haben die Einheit
        # an den Wert angehaengt ("583 ccm" / "583 ccm ccm" bei Einheit "ccm").
        from app.routes import strip_unit_suffix

        polluted = connection.exec_driver_sql(
            """
            SELECT id, wert, einheit FROM technical_spec
            WHERE einheit IS NOT NULL AND einheit != ''
              AND wert IS NOT NULL
              AND LOWER(wert) LIKE '% ' || LOWER(einheit)
            """
        ).all()
        for spec_id, wert, einheit in polluted:
            cleaned = strip_unit_suffix(wert, einheit)
            if cleaned != wert:
                connection.exec_driver_sql(
                    "UPDATE technical_spec SET wert = :wert WHERE id = :id",
                    {"wert": cleaned, "id": spec_id},
                )

        connection.exec_driver_sql(
            """
            INSERT INTO motorcycle_image (motorcycle_id, path, original_name, position, created_at)
            SELECT motorcycle.id, motorcycle.bild, NULL, 0, COALESCE(motorcycle.updated_at, motorcycle.created_at, CURRENT_TIMESTAMP)
            FROM motorcycle
            WHERE motorcycle.bild IS NOT NULL
              AND motorcycle.bild != ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM motorcycle_image
                  WHERE motorcycle_image.motorcycle_id = motorcycle.id
                    AND motorcycle_image.path = motorcycle.bild
              )
            """
        )
        connection.exec_driver_sql(
            """
            UPDATE motorcycle
            SET bild = (
                SELECT motorcycle_image.path
                FROM motorcycle_image
                WHERE motorcycle_image.motorcycle_id = motorcycle.id
                ORDER BY motorcycle_image.position, motorcycle_image.id
                LIMIT 1
            )
            WHERE (motorcycle.bild IS NULL OR motorcycle.bild = '')
              AND EXISTS (
                  SELECT 1
                  FROM motorcycle_image
                  WHERE motorcycle_image.motorcycle_id = motorcycle.id
              )
            """
        )
        connection.commit()


def ensure_admin(public_hosting=False):
    from app.models import User
    from sqlalchemy.exc import IntegrityError

    admins = User.query.filter_by(is_admin=True).all()
    if admins:
        for admin_user in admins:
            if admin_user.check_password(DEFAULT_ADMIN_PASSWORD):
                if public_hosting:
                    raise RuntimeError(
                        "Aendere das bekannte Default-Admin-Passwort, bevor MOTODB_PUBLIC_HOSTING aktiv ist."
                    )
                flag_default_admin_password(admin_user)
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
            existing_user.consent_accepted_at = existing_user.consent_accepted_at or utcnow()
            existing_user.set_password(admin_password)
            db.session.commit()
            return

        admin = User(
            username=admin_username,
            email=admin_email,
            is_admin=True,
            consent_accepted_at=utcnow(),
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
        existing_user.consent_accepted_at = existing_user.consent_accepted_at or utcnow()
        db.session.commit()
        return

    admin = User(
        username="admin",
        email=DEFAULT_ADMIN_EMAIL,
        is_admin=True,
        consent_accepted_at=utcnow(),
    )
    admin.set_password(DEFAULT_ADMIN_PASSWORD)
    db.session.add(admin)
    try:
        db.session.commit()
        print("WARNUNG: Default Admin erstellt: admin@localhost / change-me-please")
        flag_default_admin_password(admin)
    except IntegrityError:
        db.session.rollback()


def flag_default_admin_password(user):
    """Merkt sich, dass dieser Admin noch das bekannte Default-Passwort nutzt.

    Im Heimnetz-Modus blockiert das den Start nicht, aber jeder im Netz kennt
    die Kombination aus der Doku. Der Admin sieht deshalb auf jeder Seite einen
    Hinweis. Gemerkt wird der Hash: sobald das Passwort (in irgendeinem
    Gunicorn-Worker) geaendert wurde, passt der Hash nicht mehr und der Hinweis
    verschwindet ueberall ohne weitere Abstimmung.
    """
    from flask import current_app

    current_app.config.setdefault("MOTODB_DEFAULT_PASSWORD_HASHES", {})[user.id] = user.password_hash
    current_app.logger.warning(
        "Admin-Konto %s nutzt noch das Default-Passwort '%s'. Bitte umgehend aendern.",
        user.email,
        DEFAULT_ADMIN_PASSWORD,
    )


def uses_default_admin_password(user):
    """Fuer das Banner in base.html: Nutzer ist als Default-Passwort-Admin gemerkt."""
    if not user or not user.is_authenticated:
        return False
    from flask import current_app

    known_hash = current_app.config.get("MOTODB_DEFAULT_PASSWORD_HASHES", {}).get(user.id)
    return known_hash is not None and known_hash == user.password_hash


def ensure_default_settings():
    from app.models import AppSetting

    if not db.session.get(AppSetting, "backup_path"):
        db.session.add(
            AppSetting(
                key="backup_path",
                value="/PFAD/ZUM/SICHERUNGSORDNER",
            )
        )
        db.session.commit()
