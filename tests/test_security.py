import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import Motorcycle, User


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


if __name__ == "__main__":
    unittest.main()
