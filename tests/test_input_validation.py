import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

from app import create_app, db
from app.models import AppSetting, Motorcycle, ServiceChecklist, ServiceEntry, TechnicalSpec, User
from app.routes import latest_service_mileage, reconcile_all_motorcycle_mileages, safe_next_url, strip_unit_suffix


class InputValidationTestCase(unittest.TestCase):
    """Fehlerhafte Eingaben duerfen keine 500er erzeugen (Formulare und JSON-API)."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        env = {
            "DATABASE_URL": f"sqlite:///{os.path.join(self.tempdir.name, 'motodb.sqlite3')}",
            "MOTORRAD_INSTANCE_PATH": os.path.join(self.tempdir.name, "instance"),
            "MOTORRAD_UPLOAD_FOLDER": os.path.join(self.tempdir.name, "uploads"),
            "SECRET_KEY": "test-secret-key-for-validation-tests",
            "MOTODB_MAX_STORAGE_MB": "200",
        }
        with patch.dict(os.environ, env, clear=True):
            self.app = create_app()
        # Exceptions sollen wie im Betrieb zu 500 werden, nicht den Test abbrechen.
        self.app.config.update(WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=False)
        from app.auth import AUTH_ATTEMPTS
        AUTH_ATTEMPTS.clear()
        self.client = self.app.test_client()
        self.client.post("/login", data={"email": "admin@localhost", "password": "change-me-please"})
        response = self.client.post("/motorrad/neu", data={"marke": "Honda", "modell": "XL 600"})
        self.motorrad_id = int(response.headers["Location"].rsplit("/", 1)[1])

    def tearDown(self):
        self.tempdir.cleanup()

    def post_json(self, url, payload, raw=None):
        return self.client.post(url, data=raw if raw is not None else json.dumps(payload), content_type="application/json")

    def test_safe_next_url_rejects_protocol_relative_variants(self):
        self.assertEqual(safe_next_url("/motorrad/1#tab-dokumente"), "/motorrad/1#tab-dokumente")
        self.assertIsNone(safe_next_url("//evil.example"))
        self.assertIsNone(safe_next_url("/\\evil.example"))
        self.assertIsNone(safe_next_url("https://evil.example"))
        self.assertIsNone(safe_next_url(""))

    def test_storage_limit_message_uses_configured_limit(self):
        from app.routes import MAX_USER_STORAGE_BYTES, storage_limit_message
        self.assertIn(f"{MAX_USER_STORAGE_BYTES // (1024 * 1024)} MB", storage_limit_message("– Test."))

    def test_invalid_form_dates_redirect_back_with_message(self):
        service_url = f"/motorrad/{self.motorrad_id}/service/neu"
        response = self.client.post(service_url, data={"titel": "Test", "datum": "13.09.2026", "kategorie": "Sonstiges"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(service_url))
        page = self.client.get(service_url)
        self.assertIn("Ungültiges Datum", page.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(ServiceEntry.query.count(), 0)

        edit_url = f"/motorrad/{self.motorrad_id}/bearbeiten"
        response = self.client.post(edit_url, data={"marke": "Honda", "modell": "XL 600", "kaufdatum": "2026-13-45"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(edit_url))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Motorcycle, self.motorrad_id).kaufdatum)

        checklist_url = f"/motorrad/{self.motorrad_id}/checklisten/neu"
        response = self.client.post(checklist_url, data={"titel": "Check", "datum": "gestern"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(checklist_url))

    def test_api_rejects_malformed_payloads_with_400(self):
        response = self.post_json("/api/services", None, raw="[1, 2]")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

        response = self.post_json("/api/services", None, raw="kein json")
        self.assertEqual(response.status_code, 400)

        response = self.post_json("/api/services", {"titel": "ohne motorrad"})
        self.assertEqual(response.status_code, 404)

        response = self.post_json("/api/services", {"motorrad_id": self.motorrad_id, "datum": "gestern"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Datum", response.get_json()["error"])

        response = self.post_json("/api/sync", None, raw="[]")
        self.assertEqual(response.status_code, 400)

    def test_api_sync_skips_invalid_items_and_reports_them(self):
        payload = {
            "services": [
                {"motorrad_id": self.motorrad_id, "titel": "Gut", "datum": "2026-09-01", "kilometerstand": "1200"},
                {"motorrad_id": self.motorrad_id, "titel": "Schlecht", "datum": "gestern"},
                {"motorrad_id": 9999, "titel": "Fremd", "datum": "2026-09-01"},
                "kein-objekt",
            ],
            "checklist_services": [{"motorrad_id": self.motorrad_id, "checklist_id": 9999}],
        }
        response = self.post_json("/api/sync", payload)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["created"]), 1)
        self.assertEqual(body["created"][0]["titel"], "Gut")
        self.assertEqual(body["accepted"], {"services": [0], "checklist_services": []})
        self.assertEqual(body["rejected"], {"services": [1, 2, 3], "checklist_services": [0]})
        with self.app.app_context():
            self.assertEqual(ServiceEntry.query.count(), 1)

    def test_registration_validates_email_and_requires_consent(self):
        client = self.app.test_client()
        base = {"username": "neu", "password": "12345678", "password_confirm": "12345678", "consent": "on"}

        client.post("/register", data={**base, "email": "keine-mail"})
        client.post("/register", data={**base, "email": "neu@example.com", "consent": ""})
        with self.app.app_context():
            self.assertIsNone(User.query.filter_by(username="neu").first())

        client.post("/register", data={**base, "email": "  Neu@Example.COM "})
        with self.app.app_context():
            user = User.query.filter_by(username="neu").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.email, "neu@example.com")
            self.assertIsNotNone(user.consent_accepted_at)

        # Doppelte E-Mail wird unabhaengig von Gross-/Kleinschreibung erkannt.
        client.post("/register", data={**base, "username": "neu2", "email": "NEU@example.com"})
        with self.app.app_context():
            self.assertIsNone(User.query.filter_by(username="neu2").first())

        # Login ignoriert Gross-/Kleinschreibung der E-Mail.
        response = client.post("/login", data={"email": "NEU@Example.com", "password": "12345678"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/"))

    def test_strip_unit_suffix(self):
        self.assertEqual(strip_unit_suffix("583 ccm", "ccm"), "583")
        self.assertEqual(strip_unit_suffix("583 ccm ccm", "ccm"), "583")
        self.assertEqual(strip_unit_suffix("583 CCM", "ccm"), "583")
        self.assertEqual(strip_unit_suffix("583", "ccm"), "583")
        self.assertEqual(strip_unit_suffix("5-Gang", "g"), "5-Gang")
        self.assertEqual(strip_unit_suffix("90/90-21", ""), "90/90-21")

    def test_data_sheet_autosave_keeps_value_and_unit_separate(self):
        with self.app.app_context():
            db.session.add(TechnicalSpec(motorrad_id=self.motorrad_id, user_id=1, name="Hubraum", wert="583", einheit="ccm", kategorie="Motor"))
            db.session.commit()
        page = self.client.get(f"/motorrad/{self.motorrad_id}").get_data(as_text=True)
        self.assertIn('name="wert" value="583"', page)
        self.assertIn('<span class="spec-row__unit">ccm</span>', page)

        # Zweimal speichern, wie es das Autosave im Browser tut.
        for _ in range(2):
            self.client.post(
                f"/motorrad/{self.motorrad_id}/datenblatt",
                data={"name": "Hubraum", "wert": "600", "einheit": "ccm", "kategorie": "Motor", "quelle": ""},
            )
        with self.app.app_context():
            spec = TechnicalSpec.query.filter_by(motorrad_id=self.motorrad_id).one()
            self.assertEqual((spec.wert, spec.einheit), ("600", "ccm"))

        # Alte, kombinierte Eingabe wird beim Speichern bereinigt.
        self.client.post(
            f"/motorrad/{self.motorrad_id}/datenblatt",
            data={"name": "Hubraum", "wert": "650 ccm ccm", "einheit": "ccm", "kategorie": "Motor", "quelle": ""},
        )
        with self.app.app_context():
            spec = TechnicalSpec.query.filter_by(motorrad_id=self.motorrad_id).one()
            self.assertEqual((spec.wert, spec.einheit), ("650", "ccm"))

    def test_schema_update_cleans_duplicated_units(self):
        from app import ensure_schema_updates
        with self.app.app_context():
            db.session.add(TechnicalSpec(motorrad_id=self.motorrad_id, user_id=1, name="Hubraum", wert="583 ccm ccm", einheit="ccm"))
            db.session.add(TechnicalSpec(motorrad_id=self.motorrad_id, user_id=1, name="Getriebe", wert="5-Gang", einheit="g"))
            db.session.commit()
            ensure_schema_updates()
            db.session.expire_all()
            values = {spec.name: spec.wert for spec in TechnicalSpec.query.all()}
        self.assertEqual(values, {"Hubraum": "583", "Getriebe": "5-Gang"})

    def test_mileage_ignores_checklist_interval_and_prefers_latest_entry(self):
        with self.app.app_context():
            db.session.add(ServiceEntry(motorrad_id=self.motorrad_id, user_id=1, datum=date(2026, 1, 1), kilometerstand=500, kategorie="Sonstiges"))
            db.session.add(ServiceChecklist(motorrad_id=self.motorrad_id, user_id=1, titel="10.000 km Service", intervall_km=10000, is_template=False, completed_at=datetime(2026, 6, 1)))
            db.session.commit()
            self.assertEqual(latest_service_mileage(self.motorrad_id), 500)

            db.session.add(ServiceChecklist(motorrad_id=self.motorrad_id, user_id=1, titel="Saisoncheck", kilometerstand=1200, is_template=False, datum=date(2026, 3, 1)))
            db.session.add(ServiceEntry(motorrad_id=self.motorrad_id, user_id=1, datum=date(2026, 2, 1), kilometerstand=900, kategorie="Sonstiges"))
            db.session.commit()
            self.assertEqual(latest_service_mileage(self.motorrad_id), 1200)

            # Vorlagen zaehlen nie, auch nicht mit Kilometerstand.
            db.session.add(ServiceChecklist(motorrad_id=self.motorrad_id, user_id=1, titel="Vorlage", kilometerstand=99999, is_template=True))
            db.session.commit()
            self.assertEqual(latest_service_mileage(self.motorrad_id), 1200)

            # Startup-Abgleich korrigiert einen falschen, gespeicherten Stand.
            motorcycle = db.session.get(Motorcycle, self.motorrad_id)
            motorcycle.kilometerstand = 10000
            db.session.commit()
            self.assertEqual(reconcile_all_motorcycle_mileages(), 1)
            self.assertEqual(db.session.get(Motorcycle, self.motorrad_id).kilometerstand, 1200)

    def test_checklist_record_and_delete_refresh_mileage(self):
        with self.app.app_context():
            template = ServiceChecklist(motorrad_id=self.motorrad_id, user_id=1, titel="Check", is_template=True)
            db.session.add(template)
            db.session.commit()
            template_id = template.id

        response = self.client.post(f"/checklisten/{template_id}", data={"datum": "2026-09-01", "kilometerstand": "4.200 km"})
        self.assertEqual(response.status_code, 302)
        record_id = int(response.headers["Location"].rsplit("/", 1)[1])
        with self.app.app_context():
            self.assertEqual(db.session.get(Motorcycle, self.motorrad_id).kilometerstand, 4200)

        self.client.post(f"/checklisten/{record_id}/loeschen")
        with self.app.app_context():
            self.assertIsNone(db.session.get(Motorcycle, self.motorrad_id).kilometerstand)

    def test_login_rate_limit_does_not_share_loopback_ip_between_users(self):
        with self.app.app_context():
            for name in ("anna", "ben"):
                user = User(username=name, email=f"{name}@example.com")
                user.set_password("correct-password")
                db.session.add(user)
            db.session.commit()

        # Ohne vertrauenswuerdige Proxy-Header kommt hinter Nginx alles von 127.0.0.1:
        # Fehlversuche fuer anna duerfen ben nicht sperren.
        client = self.app.test_client()
        for _ in range(5):
            client.post("/login", data={"email": "anna@example.com", "password": "falsch"})
        response = client.post("/login", data={"email": "ben@example.com", "password": "correct-password"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/"))

        # Mit echter Client-IP greift das IP-Limit weiterhin, auch ueber verschiedene E-Mails hinweg.
        attacker = self.app.test_client()
        for index in range(5):
            attacker.post("/login", data={"email": f"opfer{index}@example.com", "password": "falsch"}, environ_base={"REMOTE_ADDR": "10.0.0.5"})
        response = attacker.post(
            "/login",
            data={"email": "ben@example.com", "password": "correct-password"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
            follow_redirects=True,
        )
        self.assertIn("Zu viele Anmeldeversuche", response.get_data(as_text=True))

    def test_sync_no_longer_creates_backups_and_admin_backup_is_consistent(self):
        backup_dir = os.path.join(self.tempdir.name, "backups")
        with self.app.app_context():
            db.session.get(AppSetting, "backup_path").value = backup_dir
            db.session.commit()

        # Ein normaler Nutzer kann ueber den Sync kein Server-Backup mehr ausloesen.
        with self.app.app_context():
            user = User(username="normal", email="normal@example.com")
            user.set_password("12345678")
            db.session.add(user)
            db.session.commit()
        client = self.app.test_client()
        client.post("/login", data={"email": "normal@example.com", "password": "12345678"})
        for _ in range(3):
            self.assertEqual(client.post("/api/sync", data="{}", content_type="application/json").status_code, 200)
        self.assertFalse(os.path.exists(backup_dir))
        response = client.post("/settings/backup", follow_redirects=True)
        self.assertIn("keine Berechtigung", response.get_data(as_text=True))
        self.assertFalse(os.path.exists(backup_dir))

        # Admin: Backup enthaelt eine lesbare SQLite-Kopie mit den aktuellen Daten.
        upload_file = os.path.join(self.tempdir.name, "uploads", str(self.motorrad_id), "images", "x.jpg")
        os.makedirs(os.path.dirname(upload_file))
        with open(upload_file, "wb") as handle:
            handle.write(b"jpg")
        response = self.client.post("/settings/backup", follow_redirects=True)
        self.assertIn("Backup erstellt", response.get_data(as_text=True))
        (folder,) = os.listdir(backup_dir)
        import sqlite3
        copy = sqlite3.connect(os.path.join(backup_dir, folder, "motorcycle_service.sqlite3"))
        self.assertEqual(copy.execute("SELECT marke FROM motorcycle").fetchone(), ("Honda",))
        copy.close()
        self.assertTrue(os.path.exists(os.path.join(backup_dir, folder, "uploads", str(self.motorrad_id), "images", "x.jpg")))

        # Ohne Sicherungsort: Hinweis statt Fehler.
        with self.app.app_context():
            db.session.get(AppSetting, "backup_path").value = "/PFAD/ZUM/SICHERUNGSORDNER"
            db.session.commit()
        response = self.client.post("/settings/backup", follow_redirects=True)
        self.assertIn("zuerst einen Sicherungsort", response.get_data(as_text=True))

    def test_pages_load_no_external_resources_and_fonts_are_self_hosted(self):
        page = self.client.get("/einstellungen").get_data(as_text=True)
        self.assertNotIn("fonts.googleapis.com", page)
        self.assertNotRegex(page, r'(src|href)="https?://')

        with self.client.get("/static/css/app.css") as response:
            css = response.get_data(as_text=True)
        font_files = re.findall(r'url\("\.\./fonts/([^"]+)"\)', css)
        self.assertGreaterEqual(len(font_files), 7)
        for filename in font_files:
            with self.client.get(f"/static/fonts/{filename}") as response:
                self.assertEqual(response.status_code, 200, filename)
                self.assertEqual(response.mimetype, "font/woff2", filename)
        with self.client.get("/static/fonts/LICENSE.txt") as response:
            self.assertEqual(response.status_code, 200)

        # Strikte CSP bleibt: Fonts kommen von 'self' (font-src faellt auf default-src zurueck).
        csp = self.client.get("/einstellungen").headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertNotIn("googleapis", csp)

    def test_schema_update_drops_legacy_aktiv_column_and_audit_log(self):
        import sqlite3
        from app import ensure_schema_updates

        db_path = os.path.join(self.tempdir.name, "motodb.sqlite3")
        raw = sqlite3.connect(db_path)
        raw.execute("ALTER TABLE motorcycle ADD COLUMN aktiv BOOLEAN NOT NULL DEFAULT 1")
        raw.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, action VARCHAR(80))")
        raw.commit()
        raw.close()

        with self.app.app_context():
            ensure_schema_updates()

        raw = sqlite3.connect(db_path)
        columns = {row[1] for row in raw.execute("PRAGMA table_info(motorcycle)")}
        tables = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        raw.close()
        self.assertNotIn("aktiv", columns)
        self.assertNotIn("audit_log", tables)

        # Neue Motorraeder lassen sich danach weiterhin anlegen.
        response = self.client.post("/motorrad/neu", data={"marke": "BMW", "modell": "R1100RS"})
        self.assertEqual(response.status_code, 302)

    def test_health_endpoint_reports_database_state(self):
        client = self.app.test_client()  # ohne Login
        with client.get("/health") as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"status": "ok"})

        with patch("app.db.session.execute", side_effect=RuntimeError("db down")):
            with client.get("/health") as response:
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.get_json()["status"], "error")

    def test_pwa_manifest_icons_and_offline_fallback(self):
        client = self.app.test_client()  # ohne Login
        with client.get("/manifest.webmanifest") as response:
            self.assertEqual(response.status_code, 200)
            manifest = json.loads(response.get_data(as_text=True))
        self.assertGreaterEqual(len(manifest["icons"]), 2)
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in manifest["icons"]))
        for icon in manifest["icons"]:
            with client.get(icon["src"]) as response:
                self.assertEqual(response.status_code, 200, icon["src"])
                self.assertEqual(response.mimetype, icon["type"], icon["src"])

        with client.get("/offline") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("Du bist offline", response.get_data(as_text=True))

        with client.get("/service-worker.js") as response:
            worker = response.get_data(as_text=True)
        self.assertIn('OFFLINE_URL = "/offline"', worker)
        self.assertNotIn('caches.match("/")', worker)

        page = self.client.get("/einstellungen").get_data(as_text=True)
        self.assertIn('rel="apple-touch-icon"', page)
        self.assertIn('icons/icon.svg', page)

    def test_removed_legacy_image_route_is_gone(self):
        response = self.client.post(f"/motorrad/{self.motorrad_id}/bild-loeschen")
        self.assertEqual(response.status_code, 404)

    def test_global_and_per_motorcycle_routes_share_one_handler(self):
        """/checklisten/neu, /checklisten/import und /technik sind dieselben Handler
        wie die Varianten mit Motorrad in der URL; url_for liefert beide URLs."""
        with self.app.test_request_context():
            from flask import url_for
            self.assertEqual(url_for("main.checklist_new"), "/checklisten/neu")
            self.assertEqual(url_for("main.checklist_new", motorrad_id=7), "/motorrad/7/checklisten/neu")
            self.assertEqual(url_for("main.checklist_import"), "/checklisten/import")
            self.assertEqual(url_for("main.technical_data"), "/technik")
            self.assertEqual(url_for("main.technical_data", motorrad_id=7), "/motorrad/7/technik")

        for url in ("/checklisten/neu", "/checklisten/import", "/technik",
                    f"/motorrad/{self.motorrad_id}/checklisten/neu",
                    f"/motorrad/{self.motorrad_id}/checklisten/import",
                    f"/motorrad/{self.motorrad_id}/technik"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

        # Globale Variante ohne Motorrad in der URL: Auswahl aus dem Formular.
        response = self.client.post(
            "/checklisten/neu",
            data={"motorrad_id": self.motorrad_id, "titel": "Global", "item_text": ["Punkt A"]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/motorrad/{self.motorrad_id}/checklisten"))
        response = self.client.post(
            "/technik",
            data={"motorrad_id": self.motorrad_id, "name": ["Hubraum"], "wert": ["583"], "einheit": ["ccm"], "kategorie": ["Motor"]},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(ServiceChecklist.query.filter_by(titel="Global").count(), 1)
            self.assertEqual(TechnicalSpec.query.filter_by(motorrad_id=self.motorrad_id, name="Hubraum").count(), 1)

    def test_checklist_form_selection_wins_over_url_but_only_for_own_motorcycles(self):
        response = self.client.post("/motorrad/neu", data={"marke": "BMW", "modell": "R1100RS"})
        second_id = int(response.headers["Location"].rsplit("/", 1)[1])

        # Im Formular ein anderes eigenes Motorrad gewaehlt: dort landet die Vorlage.
        response = self.client.post(
            f"/motorrad/{self.motorrad_id}/checklisten/neu",
            data={"motorrad_id": second_id, "titel": "Umgehaengt", "item_text": ["Punkt"]},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            checklist = ServiceChecklist.query.filter_by(titel="Umgehaengt").one()
            self.assertEqual(checklist.motorrad_id, second_id)

        # Fremdes Motorrad im Formular: 403, nichts angelegt.
        with self.app.app_context():
            other = User(username="other", email="other@example.com")
            other.set_password("12345678")
            db.session.add(other)
            db.session.flush()
            foreign = Motorcycle(user_id=other.id, marke="KTM", modell="690")
            db.session.add(foreign)
            db.session.commit()
            foreign_id = foreign.id
        for url in (f"/motorrad/{self.motorrad_id}/checklisten/neu", "/checklisten/neu", "/technik"):
            response = self.client.post(url, data={"motorrad_id": foreign_id, "titel": "Fremd", "item_text": ["x"]})
            self.assertEqual(response.status_code, 403, url)
        with self.app.app_context():
            self.assertEqual(ServiceChecklist.query.filter_by(titel="Fremd").count(), 0)


def _hold_startup_lock(lock_path, seconds):
    import fcntl
    import time

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        time.sleep(seconds)


class StartupLockTestCase(unittest.TestCase):
    def test_create_app_waits_for_other_process_holding_the_lock(self):
        import multiprocessing
        import time

        with tempfile.TemporaryDirectory() as tempdir:
            instance_path = os.path.join(tempdir, "instance")
            os.makedirs(instance_path)
            lock_path = os.path.join(instance_path, ".motodb-startup.lock")
            holder = multiprocessing.get_context("fork").Process(target=_hold_startup_lock, args=(lock_path, 1.5))
            holder.start()
            time.sleep(0.3)  # sicherstellen, dass der andere Prozess die Sperre haelt

            env = {
                "DATABASE_URL": f"sqlite:///{os.path.join(tempdir, 'motodb.sqlite3')}",
                "MOTORRAD_INSTANCE_PATH": instance_path,
                "MOTORRAD_UPLOAD_FOLDER": os.path.join(tempdir, "uploads"),
                "SECRET_KEY": "test-secret-key-for-lock-test",
            }
            started = time.monotonic()
            with patch.dict(os.environ, env, clear=True):
                create_app()
            elapsed = time.monotonic() - started
            holder.join()
            self.assertGreaterEqual(elapsed, 1.0, "create_app haette auf die Startup-Sperre warten muessen")


if __name__ == "__main__":
    unittest.main()
