import json
import os
import tempfile
import unittest
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app import create_app, db
from app.models import Motorcycle, MotorcycleImage, ServiceChecklist, ServiceChecklistItem, ServiceEntry, TechnicalSpec, User


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
            self.assertIn(b"Garage herunterladen", response.data)
            self.assertIn(b"Vorlagen", response.data)
            self.assertIn(b"Checklisten", response.data)
            self.assertIn(b"Datenblatt", response.data)
            self.assertIn(b"Upload", response.data)
            self.assertNotIn(b"-Vorlage", response.data)
            self.assertNotIn("Datenblatt öffnen".encode("utf-8"), response.data)
            self.assertNotIn(b"Checkliste anlegen", response.data)
            self.assertNotIn(b"Sicherungsort", response.data)
            self.assertNotIn(b"Speicherplatz", response.data)

    def test_admin_uses_garage_with_extra_user_management(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            with app.app_context():
                admin = User.query.filter_by(is_admin=True).one()
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.flush()
                admin_motorcycle = Motorcycle(user_id=admin.id, marke="BMW", modell="R80")
                user_motorcycle = Motorcycle(user_id=user.id, marke="Honda", modell="CB500")
                db.session.add_all([admin_motorcycle, user_motorcycle])
                db.session.flush()
                db.session.add(
                    ServiceEntry(
                        user_id=user.id,
                        motorrad_id=user_motorcycle.id,
                        datum=date(2026, 5, 24),
                        kategorie="Wartung",
                    )
                )
                db.session.add(
                    ServiceChecklist(
                        user_id=user.id,
                        motorrad_id=user_motorcycle.id,
                        titel="Jahresservice",
                        is_template=True,
                    )
                )
                db.session.commit()
                admin_id = admin.id
                user_motorcycle_id = user_motorcycle.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(admin_id)
                session["_fresh"] = True

            index_response = client.get("/")
            new_motorcycle_response = client.get("/motorrad/neu")
            users_response = client.get("/admin/users")
            settings_response = client.get("/einstellungen")

            self.assertEqual(index_response.status_code, 200)
            self.assertIn(b"Garage", index_response.data)
            self.assertIn(b"R80", index_response.data)
            self.assertNotIn(b"CB500", index_response.data)
            self.assertIn(b"Dokumente", index_response.data)
            self.assertNotIn(b"Technik", index_response.data)
            self.assertIn(b"Nutzerverwaltung", settings_response.data)
            self.assertEqual(client.get(f"/motorrad/{user_motorcycle_id}").status_code, 403)
            self.assertEqual(new_motorcycle_response.status_code, 200)
            self.assertIn(b"Motorrad anlegen", new_motorcycle_response.data)
            self.assertEqual(users_response.status_code, 200)
            self.assertIn(b"Admin", users_response.data)
            self.assertIn(b"rider@example.com", users_response.data)
            self.assertIn(b"1 Maschinen", users_response.data)
            self.assertIn(b"Sicherungsort", settings_response.data)
            self.assertNotIn(b"Speicherplatz", settings_response.data)
            self.assertNotIn(b"Administration", settings_response.data)
            self.assertIn(b"Vorlagen", settings_response.data)
            self.assertIn(b"Checklisten", settings_response.data)
            self.assertIn(b"Datenblatt", settings_response.data)
            self.assertIn(b"Upload", settings_response.data)
            self.assertNotIn(b"-Vorlage", settings_response.data)
            self.assertNotIn("Datenblatt öffnen".encode("utf-8"), settings_response.data)
            self.assertNotIn(b"Checkliste anlegen", settings_response.data)
            self.assertIn(b"Services", users_response.data)
            self.assertIn(b"Checklisten", users_response.data)
            self.assertIn(b"Speicherplatz", users_response.data)

    def test_template_downloads_match_current_upload_formats(self):
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

            checklist_response = client.get("/checklisten/csv-vorlage")
            technical_response = client.get("/technik/csv-vorlage")

            self.assertEqual(checklist_response.status_code, 200)
            self.assertEqual(checklist_response.mimetype, "application/zip")
            with zipfile.ZipFile(BytesIO(checklist_response.data)) as archive:
                self.assertEqual(set(archive.namelist()), {"checklisten.csv", "README.md"})
                checklist_csv = archive.read("checklisten.csv")
                checklist_readme = archive.read("README.md").decode("utf-8")
                self.assertIn(b"Pruefpunkt;Kommentar", checklist_csv)
                self.assertIn(b"Oelstand pruefen;", checklist_csv)
                self.assertNotIn(b"Motorrad;Titel;km;Intervall", checklist_csv)
                self.assertIn("Datei im ZIP: `checklisten.csv`", checklist_readme)
                self.assertIn("Punkteliste hochladen", checklist_readme)

            self.assertEqual(technical_response.status_code, 200)
            self.assertEqual(technical_response.mimetype, "application/zip")
            with zipfile.ZipFile(BytesIO(technical_response.data)) as archive:
                self.assertEqual(set(archive.namelist()), {"datenblatt.csv", "README.md"})
                technical_csv = archive.read("datenblatt.csv")
                technical_readme = archive.read("README.md").decode("utf-8")
                self.assertIn(b"Kategorie;Eintrag;Wert;Einheit", technical_csv)
                self.assertIn(b"Motor;Hubraum;583;ccm", technical_csv)
                self.assertNotIn(b"Quelle", technical_csv)
                self.assertIn("Datei im ZIP: `datenblatt.csv`", technical_readme)
                self.assertIn("Einheit", technical_readme)

    def test_csv_checklists_are_grouped_by_interval_in_service_form(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            app.config.update(WTF_CSRF_ENABLED=False)
            with app.app_context():
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.flush()
                motorcycle = Motorcycle(user_id=user.id, marke="BMW", modell="R80")
                db.session.add(motorcycle)
                db.session.commit()
                user_id = user.id
                motorcycle_id = motorcycle.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            csv_text = "\n".join(
                [
                    "Motorrad;Titel;km;Intervall;Position;Pruefpunkt;Kommentar",
                    "BMW R80;Service;10000;12;1;Oelstand pruefen;Motor warm",
                    "BMW R80;Service;10000;12;2;Bremsen pruefen;",
                    "BMW R80;Service;20000;24;1;Ventilspiel pruefen;",
                ]
            )
            import_response = client.post(
                f"/motorrad/{motorcycle_id}/checklisten/neu",
                data={"csv_file": (BytesIO(csv_text.encode("utf-8")), "checklisten.csv")},
                content_type="multipart/form-data",
            )

            self.assertEqual(import_response.status_code, 302)
            with app.app_context():
                checklists = ServiceChecklist.query.order_by(ServiceChecklist.intervall_km).all()
                self.assertEqual(len(checklists), 2)
                self.assertEqual([checklist.intervall_km for checklist in checklists], [10000, 20000])
                self.assertEqual([len(checklist.items) for checklist in checklists], [2, 1])

            service_response = client.get(f"/motorrad/{motorcycle_id}/service/neu")
            self.assertEqual(service_response.status_code, 200)
            self.assertIn("10.000 km / 12 Monate".encode("utf-8"), service_response.data)
            self.assertIn("20.000 km / 24 Monate".encode("utf-8"), service_response.data)
            self.assertIn(b'type="checkbox"', service_response.data)
            self.assertIn(b"checklist_erledigt_", service_response.data)
            self.assertIn("Oelstand pruefen".encode("utf-8"), service_response.data)
            self.assertIn("Ventilspiel pruefen".encode("utf-8"), service_response.data)

    def test_checklist_form_adds_points_from_uploaded_list(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            app.config.update(WTF_CSRF_ENABLED=False)
            with app.app_context():
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.flush()
                motorcycle = Motorcycle(user_id=user.id, marke="BMW", modell="R80")
                db.session.add(motorcycle)
                db.session.commit()
                user_id = user.id
                motorcycle_id = motorcycle.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            form_response = client.get(f"/motorrad/{motorcycle_id}/checklisten/neu")
            self.assertEqual(form_response.status_code, 200)
            self.assertEqual(form_response.data.count(b'name="item_text"'), 2)
            self.assertIn(b"data-add-checklist-item", form_response.data)
            self.assertIn(b"item_list_file", form_response.data)

            item_list = "\n".join(["Oelstand pruefen", "- Bremsen pruefen", "3. Kette schmieren"])
            create_response = client.post(
                f"/motorrad/{motorcycle_id}/checklisten/neu",
                data={
                    "motorrad_id": str(motorcycle_id),
                    "titel": "Importierte Punkteliste",
                    "item_list_file": (BytesIO(item_list.encode("utf-8")), "punkte.txt"),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(create_response.status_code, 302)
            with app.app_context():
                checklist = ServiceChecklist.query.one()
                self.assertEqual(checklist.titel, "Importierte Punkteliste")
                self.assertEqual([item.text for item in checklist.items], [
                    "Oelstand pruefen",
                    "Bremsen pruefen",
                    "Kette schmieren",
                ])

    def test_admin_can_delete_user_data_and_uploads(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            app.config.update(WTF_CSRF_ENABLED=False)
            with app.app_context():
                admin = User.query.filter_by(is_admin=True).one()
                user = User(username="rider", email="rider@example.com")
                user.set_password("rider-password")
                db.session.add(user)
                db.session.flush()
                motorcycle = Motorcycle(user_id=user.id, marke="Honda", modell="CB500")
                db.session.add(motorcycle)
                db.session.flush()
                db.session.add(
                    ServiceEntry(
                        user_id=user.id,
                        motorrad_id=motorcycle.id,
                        datum=date(2026, 5, 22),
                        kategorie="Wartung",
                    )
                )
                db.session.commit()

                admin_id = admin.id
                user_id = user.id
                upload_folder = Path(app.config["UPLOAD_FOLDER"]) / str(motorcycle.id)
                upload_folder.mkdir(parents=True)
                (upload_folder / "beleg.txt").write_text("delete", encoding="utf-8")

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(admin_id)
                session["_fresh"] = True

            response = client.post(f"/admin/users/{user_id}/delete")

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/admin/users")
            self.assertFalse(upload_folder.exists())
            with app.app_context():
                self.assertIsNone(db.session.get(User, user_id))
                self.assertEqual(Motorcycle.query.count(), 0)
                self.assertEqual(ServiceEntry.query.count(), 0)

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

    def test_motorcycle_gallery_management_updates_primary_image(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            app.config.update(WTF_CSRF_ENABLED=False)
            with app.app_context():
                user = User(username="gallery", email="gallery@example.com")
                user.set_password("gallery-password")
                db.session.add(user)
                db.session.flush()

                motorcycle = Motorcycle(user_id=user.id, marke="BMW", modell="R80")
                db.session.add(motorcycle)
                db.session.flush()

                first_path = f"{motorcycle.id}/images/first.jpg"
                second_path = f"{motorcycle.id}/images/second.jpg"
                upload_root = Path(app.config["UPLOAD_FOLDER"])
                (upload_root / first_path).parent.mkdir(parents=True, exist_ok=True)
                (upload_root / first_path).write_bytes(b"first-image")
                (upload_root / second_path).write_bytes(b"second-image")

                motorcycle.bild = first_path
                first_image = MotorcycleImage(motorcycle_id=motorcycle.id, path=first_path, position=0)
                second_image = MotorcycleImage(motorcycle_id=motorcycle.id, path=second_path, position=1)
                db.session.add_all([first_image, second_image])
                db.session.commit()

                user_id = user.id
                motorcycle_id = motorcycle.id
                second_image_id = second_image.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            make_primary_response = client.post(f"/motorrad/{motorcycle_id}/bilder/{second_image_id}/titelbild")

            self.assertEqual(make_primary_response.status_code, 302)
            self.assertEqual(make_primary_response.headers["Location"], f"/motorrad/{motorcycle_id}/bearbeiten")
            with app.app_context():
                updated_motorcycle = db.session.get(Motorcycle, motorcycle_id)
                self.assertEqual(updated_motorcycle.bild, second_path)

            delete_response = client.post(f"/motorrad/{motorcycle_id}/bilder/{second_image_id}/loeschen")

            self.assertEqual(delete_response.status_code, 302)
            self.assertEqual(delete_response.headers["Location"], f"/motorrad/{motorcycle_id}/bearbeiten")
            self.assertFalse((Path(app.config["UPLOAD_FOLDER"]) / second_path).exists())
            with app.app_context():
                updated_motorcycle = db.session.get(Motorcycle, motorcycle_id)
                self.assertEqual(updated_motorcycle.bild, first_path)
                self.assertEqual(MotorcycleImage.query.filter_by(motorcycle_id=motorcycle_id).count(), 1)

    def test_user_export_groups_data_by_motorcycle(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app = self.build_app(tempdir)
            with app.app_context():
                user = User(username="exporter", email="exporter@example.com")
                user.set_password("exporter-password")
                db.session.add(user)
                db.session.flush()

                motorcycle = Motorcycle(user_id=user.id, marke="Honda", modell="Transalp", bild="1/images/titel.jpg")
                db.session.add(motorcycle)
                db.session.flush()

                db.session.add(
                    MotorcycleImage(
                        motorcycle_id=motorcycle.id,
                        path=f"{motorcycle.id}/images/titel.jpg",
                        original_name="titel.jpg",
                        position=0,
                    )
                )
                db.session.add(
                    ServiceEntry(
                        user_id=user.id,
                        motorrad_id=motorcycle.id,
                        titel="Inspektion",
                        datum=date(2026, 5, 24),
                        kategorie="Wartung",
                        beleg=f"{motorcycle.id}/receipts/rechnung.pdf",
                        beleg_originalname="rechnung.pdf",
                    )
                )
                db.session.add(
                    TechnicalSpec(
                        user_id=user.id,
                        motorrad_id=motorcycle.id,
                        name="Leistung",
                        wert="50",
                        einheit="PS",
                        kategorie="Motor",
                    )
                )
                checklist = ServiceChecklist(
                    user_id=user.id,
                    motorrad_id=motorcycle.id,
                    titel="Frühjahrscheck",
                    is_template=False,
                )
                db.session.add(checklist)
                db.session.flush()
                db.session.add(ServiceChecklistItem(checklist_id=checklist.id, text="Kette prüfen", position=1))
                db.session.commit()

                upload_root = Path(app.config["UPLOAD_FOLDER"])
                image_path = upload_root / f"{motorcycle.id}/images/titel.jpg"
                receipt_path = upload_root / f"{motorcycle.id}/receipts/rechnung.pdf"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(b"image-bytes")
                receipt_path.write_bytes(b"pdf-bytes")
                user_id = user.id

            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            response = client.get("/user/export")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename=meineGarage.zip')

            with zipfile.ZipFile(BytesIO(response.data)) as archive:
                names = set(archive.namelist())
                self.assertIn("profil.json", names)
                self.assertIn("Honda_Transalp/daten.json", names)
                self.assertIn("Honda_Transalp/bilder/titel.jpg", names)
                self.assertIn("Honda_Transalp/belege/rechnung.pdf", names)

                export_json = json.loads(archive.read("Honda_Transalp/daten.json"))
                self.assertEqual(export_json["motorrad"]["modell"], "Transalp")
                self.assertEqual(len(export_json["bilder"]), 1)
                self.assertEqual(len(export_json["services"]), 1)
                self.assertEqual(len(export_json["technische_daten"]), 1)
                self.assertEqual(len(export_json["checklisten"]), 1)
                self.assertEqual(export_json["checklisten"][0]["items"][0]["text"], "Kette prüfen")


if __name__ == "__main__":
    unittest.main()
