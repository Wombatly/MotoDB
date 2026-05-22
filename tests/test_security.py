import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app, db
from app.models import Motorcycle, ServiceChecklist, ServiceChecklistItem, ServiceEntry, User


class SecurityTestCase(unittest.TestCase):
    def build_app(self, tempdir, **env_overrides):
        env = {
            "DATABASE_URL": f"sqlite:///{os.path.join(tempdir, 'motodb.sqlite3')}",
            "MOTORRAD_INSTANCE_PATH": os.path.join(tempdir, "instance"),
            "MOTORRAD_UPLOAD_FOLDER": os.path.join(tempdir, "uploads"),
            "SECRET_KEY": "test-secret-key-for-security-tests",
        }
        env.update(env_overrides)
        with patch.dict(os.environ, env, clear=True):
            app = create_app()
        app.config.update(TESTING=True)
        return app

    def test_public_hosting_requires_non_default_secret(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env = {
                "DATABASE_URL": f"sqlite:///{os.path.join(tempdir, 'motodb.sqlite3')}",
                "MOTORRAD_INSTANCE_PATH": os.path.join(tempdir, "instance"),
                "MOTODB_PUBLIC_HOSTING": "true",
            }
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                    create_app()

    def test_public_hosting_disables_registration_and_adds_browser_guards(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(
                tempdir,
                MOTODB_PUBLIC_HOSTING="true",
                MOTODB_ADMIN_USERNAME="admin",
                MOTODB_ADMIN_EMAIL="admin@example.com",
                MOTODB_ADMIN_PASSWORD="public-test-password",
            )

            client = app.test_client()
            login_response = client.get("/login", base_url="https://motodb.example")

            self.assertEqual(login_response.status_code, 200)
            self.assertEqual(client.get("/register").status_code, 404)
            self.assertIn("frame-ancestors 'none'", login_response.headers["Content-Security-Policy"])
            self.assertIn("max-age=31536000", login_response.headers["Strict-Transport-Security"])
            self.assertIn(
                "Secure",
                "; ".join(login_response.headers.getlist("Set-Cookie")),
            )

    def test_public_hosting_explains_http_login_block(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(
                tempdir,
                MOTODB_PUBLIC_HOSTING="true",
                MOTODB_ADMIN_USERNAME="admin",
                MOTODB_ADMIN_EMAIL="admin@example.com",
                MOTODB_ADMIN_PASSWORD="public-test-password",
            )
            client = app.test_client()

            login_response = client.get("/login", base_url="http://motodb.example")
            csrf_response = client.post(
                "/login",
                base_url="http://motodb.example",
                data={"email": "admin@example.com", "password": "public-test-password"},
            )

            self.assertEqual(login_response.status_code, 400)
            self.assertIn(b"HTTPS", login_response.data)
            self.assertIn(b"MOTODB_PUBLIC_HOSTING", login_response.data)
            self.assertEqual(csrf_response.status_code, 400)
            self.assertIn(b"HTTPS", csrf_response.data)

    def test_csrf_rejects_post_without_token_and_logout_is_not_get(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            client = app.test_client()

            self.assertEqual(
                client.post("/login", data={"email": "nobody@example.com", "password": "wrong"}).status_code,
                400,
            )
            self.assertEqual(client.get("/logout").status_code, 405)

    def test_uploads_require_login_and_motorcycle_ownership(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            with app.app_context():
                owner = User(username="owner", email="owner@example.com")
                owner.set_password("owner-password")
                other_user = User(username="other", email="other@example.com")
                other_user.set_password("other-password")
                db.session.add_all([owner, other_user])
                db.session.flush()
                motorcycle = Motorcycle(user_id=owner.id, marke="Honda", modell="CB500")
                db.session.add(motorcycle)
                db.session.commit()
                other_user_id = other_user.id
                motorcycle_id = motorcycle.id

            client = app.test_client()
            upload_url = f"/uploads/{motorcycle_id}/images/bild.jpg"
            self.assertEqual(client.get(upload_url).status_code, 302)

            with client.session_transaction() as session:
                session["_user_id"] = str(other_user_id)
                session["_fresh"] = True

            self.assertEqual(client.get(upload_url).status_code, 403)

    def test_user_settings_offer_profile_deletion(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            with app.app_context():
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.commit()
                user_id = user.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            response = client.get("/einstellungen")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Einstellungen", response.data)
            self.assertIn(b"Profil l", response.data)
            self.assertIn(b"Service-Checklisten", response.data)
            self.assertIn(b"Technische Daten", response.data)
            self.assertNotIn(b"Sicherungsort", response.data)

    def test_admin_starts_in_garage_without_user_service_settings(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            with app.app_context():
                admin = User.query.filter_by(is_admin=True).one()
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.flush()
                db.session.add(Motorcycle(user_id=user.id, marke="Honda", modell="CB500"))
                db.session.commit()
                admin_id = admin.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(admin_id)
                session["_fresh"] = True

            index_response = client.get("/")
            users_response = client.get("/admin/users")
            settings_response = client.get("/einstellungen")

            self.assertEqual(index_response.status_code, 200)
            self.assertIn(b"Motorr", index_response.data)
            self.assertIn(b"Garage", index_response.data)
            self.assertIn(b"CB500", index_response.data)
            self.assertNotIn(b"Nutzerverwaltung</a>", index_response.data)
            self.assertEqual(users_response.status_code, 200)
            self.assertIn(b"Nutzerverwaltung", users_response.data)
            self.assertIn(b"rider@example.com", users_response.data)
            self.assertIn(b"Sicherungsort", settings_response.data)
            self.assertNotIn(b"Service-Checklisten", settings_response.data)
            self.assertNotIn(b"Technische Daten", settings_response.data)

    def test_profile_deletion_removes_user_data_and_uploads(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            app.config.update(WTF_CSRF_ENABLED=False)
            with app.app_context():
                user = User(username="delete-me", email="delete-me@example.com")
                user.set_password("delete-me-password")
                db.session.add(user)
                db.session.flush()
                motorcycle = Motorcycle(user_id=user.id, marke="Honda", modell="CB500")
                db.session.add(motorcycle)
                db.session.flush()
                service = ServiceEntry(
                    user_id=user.id,
                    motorrad_id=motorcycle.id,
                    datum=date(2026, 5, 22),
                    kategorie="Wartung",
                )
                checklist = ServiceChecklist(
                    user_id=user.id,
                    motorrad_id=motorcycle.id,
                    titel="Jahresservice",
                )
                db.session.add_all([service, checklist])
                db.session.flush()
                db.session.add(ServiceChecklistItem(checklist_id=checklist.id, text="Oelstand", position=1))
                db.session.commit()

                user_id = user.id
                motorcycle_id = motorcycle.id
                upload_folder = Path(app.config["UPLOAD_FOLDER"]) / str(motorcycle_id)
                upload_folder.mkdir(parents=True)
                (upload_folder / "beleg.txt").write_text("delete", encoding="utf-8")

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            response = client.post("/user/delete", data={"confirmation": "jaloeschen"})

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/login")
            self.assertFalse(upload_folder.exists())
            with app.app_context():
                self.assertIsNone(db.session.get(User, user_id))
                self.assertEqual(ServiceEntry.query.count(), 0)
                self.assertEqual(ServiceChecklist.query.count(), 0)
                self.assertEqual(ServiceChecklistItem.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
