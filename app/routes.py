from datetime import date
from app.timeutils import utcnow
from io import BytesIO
from pathlib import Path
import os
import shutil
import zipfile

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_login import login_required, current_user

from app import db
from app.auth import admin_required
from app.help_content import HELP_TOPICS
from app.models import (
    AppSetting,
    Motorcycle,
    MotorcycleDocument,
    MotorcycleImage,
    ServiceChecklist,
    ServiceChecklistItem,
    ServiceEntry,
    TechnicalSpec,
)
from app.utils import (
    CATEGORIES,
    SERVICE_CHECKLIST_PRESETS,
    TECHNICAL_SPEC_SUGGESTIONS,
    InvalidDateError,
    parse_date,
    parse_checklist_csv,
    parse_checklist_item_file,
    parse_int,
    parse_technical_csv,
    save_upload,
)


bp = Blueprint("main", __name__)

def _max_storage_mb():
    """Speicherlimit pro Account in MB, konfigurierbar über MOTODB_MAX_STORAGE_MB."""
    try:
        value = int(os.environ.get("MOTODB_MAX_STORAGE_MB", "500"))
    except (TypeError, ValueError):
        return 500
    return value if value > 0 else 500


MAX_USER_STORAGE_BYTES = _max_storage_mb() * 1024 * 1024  # Limit pro Account


def storage_limit_message(suffix):
    """Einheitliche Meldung fuer das konfigurierte Speicherlimit (MOTODB_MAX_STORAGE_MB)."""
    return f"Speicherlimit von {MAX_USER_STORAGE_BYTES // (1024 * 1024)} MB erreicht {suffix}"


def require_motorcycle_ownership(motorcycle_id):
    """Verify current user owns the motorcycle."""
    motorcycle = db.get_or_404(Motorcycle, motorcycle_id)
    if motorcycle.user_id != current_user.id:
        abort(403)
    return motorcycle


def current_user_motorcycles_query():
    return Motorcycle.query.filter_by(user_id=current_user.id)


def safe_next_url(next_url):
    """Return next_url only if it is a safe, app-internal relative path."""
    # "//host" und "/\host" werden von Browsern als protokoll-relative URL
    # interpretiert und waeren ein Open Redirect.
    if next_url and next_url.startswith("/") and not next_url.startswith(("//", "/\\")):
        return next_url
    return None


def resolve_motorcycle(motorcycles, selected_id):
    """Return the owned motorcycle for selected_id, else the first one, else None."""
    if selected_id:
        return current_user_motorcycles_query().filter_by(id=selected_id).first()
    return motorcycles[0] if motorcycles else None


def template_zip_response(zip_filename, files):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_filename,
    )


DEFAULT_CHECKLIST_CSV = "\n".join(
    [
        "Pruefpunkt;Kommentar",
        "Oelstand pruefen;Motor warmfahren und auf ebenem Untergrund pruefen",
        "Bremsbelaege pruefen;Vorne und hinten Sichtpruefung durchfuehren",
        "Reifendruck pruefen;Herstellerangaben beachten",
    ]
)

CHECKLIST_TEMPLATE_README = """Checklisten-Vorlage

Datei im ZIP: checklisten.csv

Kurzanleitung:
- In die App gehen: Profil > Upload > Checklisten.
- Titel, Motorrad und Intervall in der App setzen.
- Die Datei bei "Punkteliste einlesen" auswählen.
- Dateiname ist egal. Wichtig ist der Inhalt der Spalten.

Spalten:
- Pruefpunkt: Der Text der Aufgabe. Daraus wird später eine Checkbox im Service.
- Kommentar: Optionaler Hinweis zur Aufgabe.

Du kannst Punkte ergänzen, löschen oder umbenennen.
"""

DEFAULT_TECHNICAL_CSV = "\n".join(
    [
        "Kategorie;Eintrag;Wert;Einheit",
        "Motor;Hubraum;583;ccm",
        "Motor;Leistung;50;PS",
        "Motor;Drehmoment;53;Nm",
        "Antrieb;Getriebe;5-Gang;",
        "Reifen;Reifen vorne;90/90-21;",
        "Reifen;Reifen hinten;130/80-17;",
    ]
)

TECHNICAL_TEMPLATE_README = """Datenblatt-Vorlage

Datei im ZIP: datenblatt.csv

Kurzanleitung:
- In die App gehen: Profil > Upload > Datenblatt.
- Motorrad auswählen.
- Die Datei als CSV hochladen.
- Dateiname ist egal. Wichtig ist der Inhalt der Spalten.

Spalten:
- Kategorie: Gruppiert die Angaben, zum Beispiel Motor, Reifen oder Antrieb.
- Eintrag: Name des technischen Werts, zum Beispiel Hubraum oder Leistung.
- Wert: Der konkrete Wert, zum Beispiel 583 oder 50.
- Einheit: Optional, zum Beispiel ccm, PS, Nm oder leer lassen.

Du kannst Kategorien, Einträge, Werte und Einheiten frei anpassen.
"""

DOCUMENT_CATEGORIES = [
    "Fahrzeugschein",
    "ABE",
    "Gutachten",
    "Versicherung",
    "Rechnung",
    "Sonstiges",
]


@bp.app_context_processor
def inject_settings():
    return {"backup_path": get_backup_path()}


@bp.errorhandler(InvalidDateError)
def handle_invalid_date(error):
    """Ungueltige Datumsangaben sauber beantworten statt mit 500.

    Formular-Routen sind GET+POST auf derselben URL: Rollback, Hinweis und
    zurueck auf das Formular. API-Routen bekommen JSON mit Status 400.
    """
    db.session.rollback()
    if request.path.startswith("/api/"):
        return api_error("Ungueltiges Datum. Erwartet wird das Format YYYY-MM-DD.")
    flash("Ungültiges Datum. Bitte im Format JJJJ-MM-TT eingeben.", "danger")
    return redirect(request.full_path.rstrip("?"))


def api_error(message, status=400):
    return jsonify({"error": message}), status


def api_json_object():
    """JSON-Body als dict; None, wenn kein JSON-Objekt gesendet wurde."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


# Hilfetexte als Jinja-Globals registrieren (NICHT als Context-Processor):
# Mit `{% from "_macros.html" import ... %}` importierte Macros sehen nur
# Environment-Globals, keine Context-Processor-Variablen.
@bp.app_template_global("help_topic")
def help_topic(key):
    return HELP_TOPICS.get(key)


@bp.app_template_global("help_topics")
def help_topics():
    return HELP_TOPICS


@bp.app_template_filter("number")
def number_filter(value):
    if value in (None, ""):
        return "-"
    return f"{int(value):,}".replace(",", ".")


@bp.app_template_filter("currency")
def currency_filter(value):
    if value in (None, ""):
        return "-"
    return f"{number_filter(value)} €"


@bp.app_template_filter("km")
def km_filter(value):
    if value in (None, ""):
        return "-"
    return f"{number_filter(value)} km"


@bp.app_template_filter("checklist_interval")
def checklist_interval_filter(checklist):
    parts = []
    if checklist.intervall_km:
        parts.append(km_filter(checklist.intervall_km))
    if checklist.intervall_monate:
        parts.append(f"{number_filter(checklist.intervall_monate)} Monate")
    return " / ".join(parts) if parts else "Ohne Intervall"


@bp.app_template_filter("filesize")
def filesize_filter(value):
    if value in (None, ""):
        return "-"
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024


@bp.app_template_filter("date_de")
def date_filter(value):
    if not value:
        return "-"
    return value.strftime("%d.%m.%Y")


@bp.app_template_filter("datetime_de")
def datetime_filter(value):
    if not value:
        return "-"
    return value.strftime("%d.%m.%Y, %H:%M")


@bp.route("/")
@login_required
def index():
    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    return render_template("motorcycles/index.html", motorcycles=motorcycles)


@bp.route("/settings/backup-path", methods=["POST"])
@login_required
@admin_required
def backup_path_update():
    setting = db.session.get(AppSetting, "backup_path")
    if not setting:
        setting = AppSetting(key="backup_path")
        db.session.add(setting)
    setting.value = request.form.get("backup_path", "").strip() or BACKUP_PATH_PLACEHOLDER
    db.session.commit()
    return redirect(url_for("main.settings"))


@bp.route("/settings/backup", methods=["POST"])
@login_required
@admin_required
def backup_create():
    try:
        target = create_server_backup()
    except BackupError as error:
        flash(str(error), "danger")
    else:
        flash(f"Backup erstellt: {target}", "success")
    return redirect(url_for("main.settings"))


@bp.route("/einstellungen")
@login_required
def settings():
    storage_used = user_storage_usage_bytes(current_user.id)
    storage_percent = (
        min(round(storage_used / MAX_USER_STORAGE_BYTES * 100), 100)
        if MAX_USER_STORAGE_BYTES
        else 0
    )
    return render_template(
        "settings.html",
        storage_used=storage_used,
        storage_limit=MAX_USER_STORAGE_BYTES,
        storage_percent=storage_percent,
    )


@bp.route("/datenschutz")
def privacy():
    return render_template("privacy.html")


@bp.route("/health")
def health():
    """Fuer Docker-HEALTHCHECK und Monitoring: App antwortet und DB ist erreichbar."""
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        return jsonify({"status": "error", "database": "unreachable"}), 503
    return jsonify({"status": "ok"})


@bp.route("/hilfe")
@login_required
def help_page():
    return render_template("help.html")


@bp.route("/dokumente", methods=["GET", "POST"])
@login_required
def documents():
    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    if request.method == "POST":
        motorcycle = require_motorcycle_ownership(parse_int(request.form.get("motorrad_id")))
        next_url = safe_next_url(request.form.get("next"))
        success_redirect = redirect(next_url or url_for("main.documents", motorrad_id=motorcycle.id))
        document_file = request.files.get("document")
        if storage_quota_exceeded(current_user.id, [document_file]):
            flash(storage_limit_message("– bitte lösche zuerst Dateien."), "danger")
            return success_redirect
        document_path, original_name = save_upload(document_file, motorcycle.id, "documents")
        if document_path:
            title = request.form.get("titel", "").strip() or original_name or "Dokument"
            category = request.form.get("kategorie") or "Sonstiges"
            db.session.add(
                MotorcycleDocument(
                    user_id=current_user.id,
                    motorrad_id=motorcycle.id,
                    titel=title,
                    kategorie=category,
                    path=document_path,
                    original_name=original_name,
                )
            )
            db.session.commit()
        return success_redirect

    motorcycle = resolve_motorcycle(motorcycles, parse_int(request.args.get("motorrad_id")))
    documents = []
    if motorcycle:
        documents = (
            MotorcycleDocument.query.filter_by(user_id=current_user.id, motorrad_id=motorcycle.id)
            .order_by(MotorcycleDocument.created_at.desc(), MotorcycleDocument.id.desc())
            .all()
        )
    return render_template(
        "documents/index.html",
        motorcycles=motorcycles,
        motorcycle=motorcycle,
        documents=documents,
        document_categories=DOCUMENT_CATEGORIES,
    )


@bp.route("/dokumente/<int:document_id>/loeschen", methods=["POST"])
@login_required
def document_delete(document_id):
    document = db.get_or_404(MotorcycleDocument, document_id)
    if document.user_id != current_user.id:
        abort(403)
    motorrad_id = document.motorrad_id
    delete_upload_file(document.path)
    db.session.delete(document)
    db.session.commit()
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("main.documents", motorrad_id=motorrad_id))


@bp.route("/motorrad/<int:motorrad_id>/dokumente/neu")
@login_required
def document_new(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    return render_template(
        "documents/form.html",
        motorcycle=motorcycle,
        document_categories=DOCUMENT_CATEGORIES,
    )


@bp.route("/checklisten/neu", methods=["GET", "POST"])
@login_required
def checklist_new_global():
    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    if request.method == "POST":
        motorrad_id = parse_int(request.form.get("motorrad_id"))
        motorcycle = require_motorcycle_ownership(motorrad_id)
        checklist = create_checklist_from_form(motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    selected_motorcycle = resolve_motorcycle(motorcycles, parse_int(request.args.get("motorrad_id")))
    preset_key = request.args.get("preset", "")
    preset = SERVICE_CHECKLIST_PRESETS.get(preset_key, {})
    return render_template(
        "checklists/form.html",
        motorcycle=selected_motorcycle,
        motorcycles=motorcycles,
        preset_key=preset_key,
        preset=preset,
        presets=SERVICE_CHECKLIST_PRESETS,
    )


@bp.route("/checklisten/import", methods=["GET", "POST"])
@login_required
def checklist_import_global():
    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    if request.method == "POST":
        imported = create_checklists_from_csv(request.files.get("csv_file"))
        if imported:
            db.session.commit()
            return redirect(url_for("main.checklist_index", motorrad_id=imported[0].motorrad_id))

        motorrad_id = parse_int(request.form.get("motorrad_id"))
        motorcycle = require_motorcycle_ownership(motorrad_id)
        checklist = create_checklist_from_form(motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    selected_motorcycle = resolve_motorcycle(motorcycles, parse_int(request.args.get("motorrad_id")))
    return render_template(
        "checklists/import.html",
        motorcycle=selected_motorcycle,
        motorcycles=motorcycles,
    )


@bp.route("/checklisten/csv-vorlage")
@login_required
def checklist_csv_template():
    return template_zip_response(
        "checklisten_vorlage.zip",
        {
            "checklisten.csv": DEFAULT_CHECKLIST_CSV + "\n",
            "README.txt": CHECKLIST_TEMPLATE_README,
        },
    )


@bp.route("/technik", methods=["GET", "POST"])
@login_required
def technical_data_global():
    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    motorcycle = resolve_motorcycle(motorcycles, parse_int(request.values.get("motorrad_id")))

    if request.method == "POST":
        motorrad_id = parse_int(request.form.get("motorrad_id"))
        motorcycle = require_motorcycle_ownership(motorrad_id)
        save_technical_specs(motorcycle)
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))

    specs, suggestions = get_technical_context(motorcycle) if motorcycle else ([], [])
    return render_template(
        "motorcycles/technical.html",
        motorcycle=motorcycle,
        motorcycles=motorcycles,
        specs=specs,
        suggestions=suggestions,
    )


@bp.route("/technik/csv-vorlage")
@login_required
def technical_csv_template():
    return template_zip_response(
        "datenblatt_vorlage.zip",
        {
            "datenblatt.csv": DEFAULT_TECHNICAL_CSV + "\n",
            "README.txt": TECHNICAL_TEMPLATE_README,
        },
    )


@bp.route("/motorrad/neu", methods=["GET", "POST"])
@login_required
def motorcycle_new():
    motorcycle = Motorcycle()
    if request.method == "POST":
        fill_motorcycle(motorcycle)
        motorcycle.user_id = current_user.id
        db.session.add(motorcycle)
        db.session.flush()
        uploaded_images = request.files.getlist("bilder") or [request.files.get("bild")]
        if storage_quota_exceeded(current_user.id, uploaded_images):
            flash(storage_limit_message("– Bilder wurden nicht gespeichert."), "danger")
        else:
            add_motorcycle_images(motorcycle, uploaded_images)
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))
    return render_template("motorcycles/form.html", motorcycle=motorcycle, title="Motorrad anlegen", gallery_images=[])


@bp.route("/motorrad/<int:motorrad_id>")
@login_required
def motorcycle_detail(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    gallery_images = ordered_motorcycle_images(motorcycle)
    primary_image = gallery_images[0] if gallery_images else None
    services = (
        ServiceEntry.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id)
        .order_by(ServiceEntry.datum.desc(), ServiceEntry.id.desc())
        .all()
    )
    total_costs = sum(entry.kosten or 0 for entry in services)
    technical_specs = (
        TechnicalSpec.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id)
        .order_by(TechnicalSpec.position, TechnicalSpec.id)
        .all()
    )
    technical_groups = []
    group_index = {}
    for spec in technical_specs:
        category = spec.kategorie or "Allgemein"
        if category not in group_index:
            group_index[category] = len(technical_groups)
            technical_groups.append((category, []))
        technical_groups[group_index[category]][1].append(spec)
    documents = (
        MotorcycleDocument.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id)
        .order_by(MotorcycleDocument.created_at.desc(), MotorcycleDocument.id.desc())
        .all()
    )
    checklist_records = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id, is_template=False)
        .order_by(ServiceChecklist.completed_at.desc().nullslast(), ServiceChecklist.id.desc())
        .limit(5)
        .all()
    )
    checklist_records = unique_checklist_records(checklist_records)

    history = []
    for service in services:
        history.append({
            "kind": "service",
            "date": service.datum,
            "id": service.id,
            "titel": service.titel or "Service",
            "kilometerstand": service.kilometerstand,
            "kosten": service.kosten,
            "intervall_km": None,
        })
    for record in checklist_records:
        history.append({
            "kind": "checklist",
            "date": record.datum or (record.completed_at.date() if record.completed_at else None),
            "id": record.id,
            "titel": record.titel,
            "kilometerstand": record.kilometerstand,
            "kosten": None,
            "intervall_km": record.intervall_km,
        })
    history.sort(key=lambda item: (item["date"] or date.min), reverse=True)

    return render_template(
        "motorcycles/detail.html",
        motorcycle=motorcycle,
        gallery_images=gallery_images,
        primary_image=primary_image,
        services=services,
        total_costs=total_costs,
        technical_specs=technical_specs,
        technical_groups=technical_groups,
        documents=documents,
        history=history,
    )


@bp.route("/motorrad/<int:motorrad_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def motorcycle_edit(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    if request.method == "POST":
        fill_motorcycle(motorcycle)
        uploaded_images = request.files.getlist("bilder") or [request.files.get("bild")]
        if storage_quota_exceeded(current_user.id, uploaded_images):
            flash(storage_limit_message("– Bilder wurden nicht gespeichert."), "danger")
        else:
            add_motorcycle_images(motorcycle, uploaded_images)
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))
    return render_template(
        "motorcycles/form.html",
        motorcycle=motorcycle,
        title="Motorrad bearbeiten",
        gallery_images=ordered_motorcycle_images(motorcycle),
    )


@bp.route("/motorrad/<int:motorrad_id>/bilder/<int:image_id>/loeschen", methods=["POST"])
@login_required
def motorcycle_gallery_image_delete(motorrad_id, image_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    image = MotorcycleImage.query.filter_by(id=image_id, motorcycle_id=motorrad_id).first_or_404()
    delete_upload_file(image.path)
    db.session.delete(image)
    db.session.flush()
    sync_motorcycle_primary_image(motorcycle)
    db.session.commit()
    return redirect(url_for("main.motorcycle_edit", motorrad_id=motorrad_id))


@bp.route("/motorrad/<int:motorrad_id>/bilder/<int:image_id>/titelbild", methods=["POST"])
@login_required
def motorcycle_gallery_image_make_primary(motorrad_id, image_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    image = MotorcycleImage.query.filter_by(id=image_id, motorcycle_id=motorrad_id).first_or_404()
    motorcycle.bild = image.path
    db.session.commit()
    return redirect(url_for("main.motorcycle_edit", motorrad_id=motorrad_id))


@bp.route("/motorrad/<int:motorrad_id>/loeschen", methods=["POST"])
@login_required
def motorcycle_delete(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    delete_motorcycle_uploads(motorcycle.id)
    db.session.delete(motorcycle)
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/motorrad/<int:motorrad_id>/technik", methods=["GET", "POST"])
@login_required
def technical_data(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    if request.method == "POST":
        form_motorcycle_id = parse_int(request.form.get("motorrad_id")) or motorrad_id
        motorcycle = require_motorcycle_ownership(form_motorcycle_id)
        save_technical_specs(motorcycle)
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))

    specs, suggestions = get_technical_context(motorcycle)
    return render_template(
        "motorcycles/technical.html",
        motorcycle=motorcycle,
        motorcycles=current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all(),
        specs=specs,
        suggestions=suggestions,
    )


@bp.route("/motorrad/<int:motorrad_id>/datenblatt", methods=["POST"])
@login_required
def motorcycle_data_sheet_update(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    save_technical_specs(motorcycle)
    return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))


@bp.route("/motorrad/<int:motorrad_id>/datenblatt/reihenfolge", methods=["POST"])
@login_required
def motorcycle_data_sheet_reorder(motorrad_id):
    require_motorcycle_ownership(motorrad_id)
    payload = request.get_json(silent=True) or {}
    specs = {
        spec.id: spec
        for spec in TechnicalSpec.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id).all()
    }
    position = 0
    for raw_id in payload.get("order", []):
        spec = specs.get(parse_int(raw_id))
        if spec is not None:
            spec.position = position
            position += 1
    db.session.commit()
    return ("", 204)


@bp.route("/motorrad/<int:motorrad_id>/checklisten")
@login_required
def checklist_index(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    checklist_templates = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id)
        .filter_by(is_template=True)
        .order_by(ServiceChecklist.datum.desc().nullslast(), ServiceChecklist.id.desc())
        .all()
    )
    return render_template(
        "checklists/index.html",
        motorcycle=motorcycle,
        checklist_templates=checklist_templates,
    )


@bp.route("/motorrad/<int:motorrad_id>/checklisten/neu", methods=["GET", "POST"])
@login_required
def checklist_new(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    preset_key = request.values.get("preset", "")
    preset = SERVICE_CHECKLIST_PRESETS.get(preset_key, {})

    if request.method == "POST":
        checklist = create_checklist_from_form(motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    return render_template(
        "checklists/form.html",
        motorcycle=motorcycle,
        motorcycles=current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all(),
        preset_key=preset_key,
        preset=preset,
        presets=SERVICE_CHECKLIST_PRESETS,
    )


@bp.route("/motorrad/<int:motorrad_id>/checklisten/import", methods=["GET", "POST"])
@login_required
def checklist_import(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    if request.method == "POST":
        imported = create_checklists_from_csv(request.files.get("csv_file"))
        if imported:
            db.session.commit()
            return redirect(url_for("main.checklist_index", motorrad_id=imported[0].motorrad_id))

        form_motorcycle_id = parse_int(request.form.get("motorrad_id")) or motorrad_id
        motorcycle = require_motorcycle_ownership(form_motorcycle_id)
        checklist = create_checklist_from_form(motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    return render_template(
        "checklists/import.html",
        motorcycle=motorcycle,
        motorcycles=current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all(),
    )


@bp.route("/checklisten/<int:checklist_id>", methods=["GET", "POST"])
@login_required
def checklist_edit(checklist_id):
    checklist = db.get_or_404(ServiceChecklist, checklist_id)
    require_motorcycle_ownership(checklist.motorrad_id)
    if request.method == "POST":
        if not checklist.is_template:
            abort(409)
        record = create_checklist_record_from_template(checklist)
        refresh_motorcycle_mileage(checklist.motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_edit", checklist_id=record.id))

    return render_template("checklists/edit.html", checklist=checklist, motorcycle=checklist.motorcycle)


@bp.route("/checklisten/<int:checklist_id>/vorlage-bearbeiten", methods=["GET", "POST"])
@login_required
def checklist_template_edit(checklist_id):
    checklist = db.get_or_404(ServiceChecklist, checklist_id)
    require_motorcycle_ownership(checklist.motorrad_id)
    if not checklist.is_template:
        abort(409)

    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    if request.method == "POST":
        update_checklist_from_form(checklist)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    return render_template(
        "checklists/form.html",
        motorcycle=checklist.motorcycle,
        motorcycles=motorcycles,
        preset_key="",
        preset={},
        presets=SERVICE_CHECKLIST_PRESETS,
        checklist=checklist,
    )


@bp.route("/checklisten/<int:checklist_id>/loeschen", methods=["POST"])
@login_required
def checklist_delete(checklist_id):
    checklist = db.get_or_404(ServiceChecklist, checklist_id)
    require_motorcycle_ownership(checklist.motorrad_id)
    motorrad_id = checklist.motorrad_id
    motorcycle = checklist.motorcycle
    db.session.delete(checklist)
    db.session.flush()
    refresh_motorcycle_mileage(motorcycle)
    db.session.commit()
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("main.checklist_index", motorrad_id=motorrad_id))


@bp.route("/motorrad/<int:motorrad_id>/service/neu", methods=["GET", "POST"])
@login_required
def service_new(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    service = ServiceEntry(motorrad_id=motorrad_id, datum=date.today(), user_id=current_user.id)
    checklist_templates = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id, is_template=True)
        .order_by(
            ServiceChecklist.intervall_km.asc().nullslast(),
            ServiceChecklist.intervall_monate.asc().nullslast(),
            ServiceChecklist.titel,
            ServiceChecklist.id,
        )
        .all()
    )
    if request.method == "POST":
        service_art = request.form.get("service_art", "free")
        if service_art.startswith("checklist:"):
            template_id = parse_int(service_art.split(":")[1])
            template = db.session.get(ServiceChecklist, template_id) if template_id else None
            if template and template.motorrad_id == motorrad_id and template.user_id == current_user.id:
                record = ServiceChecklist(
                    motorrad_id=motorrad_id,
                    user_id=current_user.id,
                    titel=request.form.get("titel") or template.titel,
                    intervall_km=template.intervall_km,
                    intervall_monate=template.intervall_monate,
                    datum=parse_date(request.form.get("datum")) or date.today(),
                    kilometerstand=parse_int(request.form.get("kilometerstand")),
                    anmerkungen=request.form.get("beschreibung"),
                    is_template=False,
                    source_template_id=template.id,
                    completed_at=utcnow(),
                )
                db.session.add(record)
                db.session.flush()
                completed_ids = set(request.form.getlist(f"checklist_erledigt_{template.id}"))
                for item in template.items:
                    db.session.add(
                        ServiceChecklistItem(
                            checklist_id=record.id,
                            position=item.position,
                            text=item.text,
                            kommentar_vorlage=item.kommentar_vorlage,
                            erledigt=str(item.id) in completed_ids,
                            anmerkung=request.form.get(f"checklist_anmerkung_{item.id}"),
                        )
                    )
                refresh_motorcycle_mileage(motorcycle)
                db.session.commit()
                return redirect(url_for("main.motorcycle_detail", motorrad_id=motorrad_id))
        fill_service(service)
        db.session.add(service)
        db.session.flush()
        beleg_file = request.files.get("beleg")
        if storage_quota_exceeded(current_user.id, [beleg_file]):
            flash(storage_limit_message("– Beleg wurde nicht gespeichert."), "danger")
        else:
            receipt_path, original_name = save_upload(beleg_file, motorrad_id, "receipts")
            if receipt_path:
                service.beleg = receipt_path
                service.beleg_originalname = original_name
        refresh_motorcycle_mileage(motorcycle)
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorrad_id))
    return render_template(
        "service/form.html",
        motorcycle=motorcycle,
        service=service,
        categories=CATEGORIES,
        checklist_templates=checklist_templates,
        checklist_template_groups=group_checklists_by_interval(checklist_templates),
        title="Service eintragen",
    )


@bp.route("/service/<int:service_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def service_edit(service_id):
    service = db.get_or_404(ServiceEntry, service_id)
    if service.user_id != current_user.id:
        abort(403)
    motorcycle = service.motorcycle
    if request.method == "POST":
        fill_service(service)
        beleg_file = request.files.get("beleg")
        if storage_quota_exceeded(current_user.id, [beleg_file]):
            flash(storage_limit_message("– Beleg wurde nicht gespeichert."), "danger")
        else:
            receipt_path, original_name = save_upload(beleg_file, service.motorrad_id, "receipts")
            if receipt_path:
                delete_upload_file(service.beleg)
                service.beleg = receipt_path
                service.beleg_originalname = original_name
        refresh_motorcycle_mileage(motorcycle)
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=service.motorrad_id))
    return render_template(
        "service/form.html",
        motorcycle=motorcycle,
        service=service,
        categories=CATEGORIES,
        checklist_templates=[],
        title="Service bearbeiten",
    )


@bp.route("/service/<int:service_id>/ansicht")
@login_required
def service_detail(service_id):
    service = db.get_or_404(ServiceEntry, service_id)
    if service.user_id != current_user.id:
        abort(403)
    return render_template("service/detail.html", service=service, motorcycle=service.motorcycle)


@bp.route("/service/<int:service_id>/loeschen", methods=["POST"])
@login_required
def service_delete(service_id):
    service = db.get_or_404(ServiceEntry, service_id)
    if service.user_id != current_user.id:
        abort(403)
    motorrad_id = service.motorrad_id
    motorcycle = service.motorcycle
    delete_upload_file(service.beleg)
    db.session.delete(service)
    db.session.flush()
    refresh_motorcycle_mileage(motorcycle)
    db.session.commit()
    return redirect(url_for("main.motorcycle_detail", motorrad_id=motorrad_id))


@bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    parts = Path(filename).parts
    if not parts:
        abort(404)
    try:
        motorrad_id = int(parts[0])
    except ValueError:
        abort(404)
    require_motorcycle_ownership(motorrad_id)
    resolve_upload_path(filename)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(Path(current_app.root_path) / "static", "manifest.webmanifest")


@bp.route("/service-worker.js")
def service_worker():
    return send_from_directory(Path(current_app.root_path) / "static", "service-worker.js")


@bp.route("/api/motorcycles")
def api_motorcycles():
    if not current_user.is_authenticated:
        return jsonify([])

    motorcycles = current_user_motorcycles_query().order_by(Motorcycle.marke, Motorcycle.modell).all()
    return jsonify(
        [
            {
                "id": m.id,
                "marke": m.marke,
                "modell": m.modell,
                "baujahr": m.baujahr,
                "kilometerstand": m.kilometerstand,
                "updated_at": m.updated_at.isoformat(),
            }
            for m in motorcycles
        ]
    )


@bp.route("/api/motorcycles/<int:motorrad_id>/services")
def api_services(motorrad_id):
    if not current_user.is_authenticated:
        return jsonify([])

    motorcycle = db.get_or_404(Motorcycle, motorrad_id)
    if motorcycle.user_id != current_user.id:
        abort(403)

    services = ServiceEntry.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id).order_by(ServiceEntry.datum.desc()).all()
    return jsonify([serialize_service(s) for s in services])


@bp.route("/api/services", methods=["POST"])
def api_create_service():
    if not current_user.is_authenticated:
        abort(401)

    data = api_json_object()
    if data is None:
        return api_error("JSON-Objekt erwartet.")
    motorrad_id = parse_int(data.get("motorrad_id"))
    motorcycle = db.session.get(Motorcycle, motorrad_id) if motorrad_id else None
    if not motorcycle:
        return api_error("Motorrad nicht gefunden.", 404)
    if motorcycle.user_id != current_user.id:
        abort(403)

    service = ServiceEntry(
        motorrad_id=motorcycle.id,
        user_id=current_user.id,
        titel=data.get("titel"),
        datum=parse_date(data.get("datum")) or date.today(),
        kilometerstand=parse_int(data.get("kilometerstand")),
        beschreibung=data.get("beschreibung"),
        kosten=parse_int(data.get("kosten")),
        kategorie=data.get("kategorie") or "Sonstiges",
        naechster_service_km=parse_int(data.get("naechster_service_km")),
        naechster_service_datum=parse_date(data.get("naechster_service_datum")),
    )
    db.session.add(service)
    db.session.flush()
    refresh_motorcycle_mileage(motorcycle)
    db.session.commit()
    return jsonify(serialize_service(service)), 201


@bp.route("/api/sync", methods=["POST"])
def api_sync():
    """Offline-Eintraege uebernehmen.

    Die Antwort bestaetigt jeden Eintrag einzeln ueber seinen Index in der
    gesendeten Liste ("accepted"/"rejected"), damit der Client nur wirklich
    gespeicherte Eintraege aus seinem Offline-Speicher entfernt.
    """
    if not current_user.is_authenticated:
        abort(401)

    data = api_json_object()
    if data is None:
        return api_error("JSON-Objekt erwartet.")
    created = []
    checklist_services = []
    accepted = {"services": [], "checklist_services": []}
    rejected = {"services": [], "checklist_services": []}

    def payload_list(key):
        value = data.get(key, [])
        return value if isinstance(value, list) else []

    def owned_motorcycle(item):
        motorrad_id = parse_int(item.get("motorrad_id"))
        motorcycle = db.session.get(Motorcycle, motorrad_id) if motorrad_id else None
        if motorcycle and motorcycle.user_id == current_user.id:
            return motorcycle
        return None

    for index, item in enumerate(payload_list("services")):
        motorcycle = owned_motorcycle(item) if isinstance(item, dict) else None
        if not motorcycle:
            rejected["services"].append(index)
            continue
        try:
            service = ServiceEntry(
                motorrad_id=motorcycle.id,
                user_id=current_user.id,
                titel=item.get("titel"),
                datum=parse_date(item.get("datum")) or date.today(),
                kilometerstand=parse_int(item.get("kilometerstand")),
                beschreibung=item.get("beschreibung"),
                kosten=parse_int(item.get("kosten")),
                kategorie=item.get("kategorie") or "Sonstiges",
                naechster_service_km=parse_int(item.get("naechster_service_km")),
                naechster_service_datum=parse_date(item.get("naechster_service_datum")),
            )
        except InvalidDateError:
            rejected["services"].append(index)
            continue
        db.session.add(service)
        db.session.flush()
        refresh_motorcycle_mileage(motorcycle)
        created.append(serialize_service(service))
        accepted["services"].append(index)

    for index, item in enumerate(payload_list("checklist_services")):
        motorcycle = owned_motorcycle(item) if isinstance(item, dict) else None
        checklist_id = parse_int(item.get("checklist_id")) if isinstance(item, dict) else None
        template = db.session.get(ServiceChecklist, checklist_id) if checklist_id else None
        if not motorcycle or not template or template.motorrad_id != motorcycle.id:
            rejected["checklist_services"].append(index)
            continue
        try:
            record = create_checklist_record_from_payload(template, item)
        except InvalidDateError:
            rejected["checklist_services"].append(index)
            continue
        refresh_motorcycle_mileage(motorcycle)
        checklist_services.append({"checklist_id": record.id})
        accepted["checklist_services"].append(index)

    db.session.commit()
    return jsonify(
        {
            "created": created,
            "checklist_services": checklist_services,
            "accepted": accepted,
            "rejected": rejected,
        }
    )


def fill_motorcycle(motorcycle):
    motorcycle.marke = request.form.get("marke", "").strip()
    motorcycle.modell = request.form.get("modell", "").strip()
    motorcycle.baujahr = parse_int(request.form.get("baujahr"))
    motorcycle.kaufpreis = parse_int(request.form.get("kaufpreis"))
    motorcycle.hubraum = parse_int(request.form.get("hubraum"))
    motorcycle.ps = parse_int(request.form.get("ps"))
    motorcycle.farbe = request.form.get("farbe")
    motorcycle.kaufdatum = parse_date(request.form.get("kaufdatum"))
    motorcycle.kennzeichen = request.form.get("kennzeichen")
    motorcycle.vin = request.form.get("vin")
    motorcycle.erstzulassung = parse_date(request.form.get("erstzulassung"))
    motorcycle.verkauft_am = parse_date(request.form.get("verkauft_am"))
    motorcycle.verkaufspreis = parse_int(request.form.get("verkaufspreis"))
    motorcycle.notizen = request.form.get("notizen")


def fill_service(service):
    service.titel = request.form.get("titel")
    service.datum = parse_date(request.form.get("datum")) or date.today()
    service.kilometerstand = parse_int(request.form.get("kilometerstand"))
    service.beschreibung = request.form.get("beschreibung")
    service.kosten = parse_int(request.form.get("kosten"))
    service.kategorie = request.form.get("kategorie") or "Sonstiges"
    service.naechster_service_km = parse_int(request.form.get("naechster_service_km"))
    service.naechster_service_datum = parse_date(request.form.get("naechster_service_datum"))


def unique_checklist_records(records):
    unique = []
    seen = set()
    for record in records:
        key = (
            record.titel,
            record.datum,
            record.kilometerstand,
            record.intervall_km,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def refresh_motorcycle_mileage(motorcycle):
    """Denormalisierten Kilometerstand nach jeder Aenderung an Services/Checklisten neu setzen."""
    motorcycle.kilometerstand = latest_service_mileage(motorcycle.id)


def reconcile_all_motorcycle_mileages():
    """Einmal beim Start alle Kilometerstaende neu ableiten (z. B. nach Logik-Aenderungen)."""
    changed = 0
    for motorcycle in Motorcycle.query.all():
        latest = latest_service_mileage(motorcycle.id)
        if motorcycle.kilometerstand != latest:
            motorcycle.kilometerstand = latest
            changed += 1
    if changed:
        db.session.commit()
    return changed


def latest_service_mileage(motorrad_id):
    """Juengster erfasster Kilometerstand aus Services und Checklisten-Datensaetzen.

    Zaehlt nur echte km-Angaben; das Intervall einer Checkliste ist kein
    Kilometerstand. Bei gleichem Datum gewinnt der spaeter angelegte Eintrag.
    """
    service = (
        ServiceEntry.query.filter_by(motorrad_id=motorrad_id)
        .filter(ServiceEntry.kilometerstand.isnot(None))
        .order_by(ServiceEntry.datum.desc(), ServiceEntry.id.desc())
        .first()
    )
    checklist_date = db.func.coalesce(ServiceChecklist.datum, db.func.date(ServiceChecklist.completed_at))
    checklist = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, is_template=False)
        .filter(ServiceChecklist.kilometerstand.isnot(None))
        .order_by(checklist_date.desc().nullslast(), ServiceChecklist.id.desc())
        .first()
    )

    candidates = []
    if service:
        candidates.append((service.datum or date.min, service.id, service.kilometerstand))
    if checklist:
        checklist_day = checklist.datum or (checklist.completed_at.date() if checklist.completed_at else date.min)
        candidates.append((checklist_day, checklist.id, checklist.kilometerstand))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def upload_root():
    return Path(current_app.config["UPLOAD_FOLDER"]).resolve()


def resolve_upload_path(relative_path):
    if not relative_path:
        return None
    root = upload_root()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        abort(400)
    return target


def user_storage_usage_bytes(user_id):
    """Gesamtgröße aller Upload-Dateien, die den Motorrädern des Users gehören."""
    root = upload_root()
    motorcycle_ids = [
        motorcycle_id
        for (motorcycle_id,) in Motorcycle.query.with_entities(Motorcycle.id)
        .filter_by(user_id=user_id)
        .all()
    ]
    total = 0
    for motorcycle_id in motorcycle_ids:
        folder = root / str(motorcycle_id)
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file():
                    try:
                        total += path.stat().st_size
                    except OSError:
                        continue
    return total


def incoming_upload_size(files):
    """Größe der hochzuladenden Dateien, ohne den Stream zu verbrauchen."""
    total = 0
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        stream = file_storage.stream
        try:
            position = stream.tell()
            stream.seek(0, os.SEEK_END)
            total += stream.tell()
            stream.seek(position)
        except (OSError, ValueError):
            continue
    return total


def storage_quota_exceeded(user_id, files):
    incoming = incoming_upload_size(files)
    if incoming <= 0:
        return False
    return user_storage_usage_bytes(user_id) + incoming > MAX_USER_STORAGE_BYTES


def delete_upload_file(relative_path):
    target = resolve_upload_path(relative_path)
    if target and target.is_file():
        target.unlink()


def delete_motorcycle_uploads(motorrad_id):
    root = upload_root()
    target = (root / str(motorrad_id)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        abort(400)
    if target.is_dir():
        shutil.rmtree(target)


def add_motorcycle_images(motorcycle, files):
    next_position = MotorcycleImage.query.filter_by(motorcycle_id=motorcycle.id).count()
    created = []
    for file_storage in files:
        image_path, original_name = save_upload(file_storage, motorcycle.id, "images")
        if not image_path:
            continue
        image = MotorcycleImage(
            motorcycle_id=motorcycle.id,
            path=image_path,
            original_name=original_name,
            position=next_position,
        )
        db.session.add(image)
        created.append(image)
        next_position += 1
        if not motorcycle.bild:
            motorcycle.bild = image_path
    return created


def ordered_motorcycle_images(motorcycle):
    images = list(motorcycle.images)
    if not images:
        return []
    if motorcycle.bild:
        images.sort(key=lambda image: (image.path != motorcycle.bild, image.position, image.id))
    return images


def sync_motorcycle_primary_image(motorcycle):
    images = ordered_motorcycle_images(motorcycle)
    motorcycle.bild = images[0].path if images else None


def group_checklists_by_interval(checklists):
    groups = []
    labels = {}
    for checklist in checklists:
        label = checklist_interval_filter(checklist)
        if label not in labels:
            labels[label] = {"label": label, "checklists": []}
            groups.append(labels[label])
        labels[label]["checklists"].append(checklist)
    return groups


def find_motorcycle_for_checklist_row(row):
    motorrad_id = parse_int(row.get("motorrad_id"))
    if motorrad_id:
        return current_user_motorcycles_query().filter_by(id=motorrad_id).first()

    label = (row.get("motorrad") or "").strip().lower()
    if not label:
        return None
    for motorcycle in current_user_motorcycles_query().all():
        full_name = f"{motorcycle.marke} {motorcycle.modell}".strip().lower()
        if label in {full_name, motorcycle.marke.lower(), motorcycle.modell.lower()}:
            return motorcycle
    return None


def create_checklists_from_csv(file_storage):
    rows = parse_checklist_csv(file_storage)
    grouped = {}
    for row in rows:
        motorcycle = find_motorcycle_for_checklist_row(row)
        if not motorcycle:
            continue
        interval_km = parse_int(row.get("intervall_km"))
        interval_months = parse_int(row.get("intervall_monate"))
        key = (motorcycle.id, row["titel"], interval_km, interval_months)
        grouped.setdefault(
            key,
            {
                "motorcycle": motorcycle,
                "titel": row["titel"],
                "intervall_km": interval_km,
                "intervall_monate": interval_months,
                "items": [],
            },
        )
        grouped[key]["items"].append(row)

    created = []
    for group in grouped.values():
        checklist = ServiceChecklist(
            motorrad_id=group["motorcycle"].id,
            user_id=group["motorcycle"].user_id,
            titel=group["titel"],
            intervall_km=group["intervall_km"],
            intervall_monate=group["intervall_monate"],
            is_template=True,
        )
        db.session.add(checklist)
        db.session.flush()
        items = sorted(group["items"], key=lambda item: parse_int(item.get("position")) or 9999)
        for position, item in enumerate(items, start=1):
            db.session.add(
                ServiceChecklistItem(
                    checklist_id=checklist.id,
                    position=position,
                    text=item["text"],
                    kommentar_vorlage=item.get("kommentar"),
                )
            )
        created.append(checklist)
    return created


def create_checklist_from_form(motorcycle):
    preset_key = request.form.get("preset", "")
    preset = SERVICE_CHECKLIST_PRESETS.get(preset_key, {})
    checklist = ServiceChecklist(
        motorrad_id=motorcycle.id,
        user_id=motorcycle.user_id,
        titel=request.form.get("titel") or preset.get("titel") or "Service-Checkliste",
        intervall_km=parse_int(request.form.get("intervall_km")),
        intervall_monate=parse_int(request.form.get("intervall_monate")),
        datum=parse_date(request.form.get("datum")),
        kilometerstand=parse_int(request.form.get("kilometerstand")),
        anmerkungen=request.form.get("anmerkungen"),
        is_template=True,
    )
    db.session.add(checklist)
    db.session.flush()

    item_texts = request.form.getlist("item_text")
    item_comments = request.form.getlist("item_comment")
    rows = []
    for index, text in enumerate(item_texts):
        text = text.strip()
        comment = item_comments[index].strip() if index < len(item_comments) else ""
        if text or comment:
            rows.append((text or "Prüfpunkt", comment))

    if not rows and preset:
        rows = [(item, "") for item in preset.get("items", [])]

    rows.extend(parse_checklist_item_file(request.files.get("item_list_file")))

    for position, (text, comment) in enumerate(rows, start=1):
        db.session.add(
            ServiceChecklistItem(
                checklist_id=checklist.id,
                position=position,
                text=text,
                kommentar_vorlage=comment,
            )
        )
    return checklist


def update_checklist_from_form(checklist):
    checklist.titel = request.form.get("titel") or checklist.titel or "Service-Checkliste"
    checklist.intervall_km = parse_int(request.form.get("intervall_km"))
    checklist.intervall_monate = parse_int(request.form.get("intervall_monate"))
    checklist.datum = parse_date(request.form.get("datum"))
    checklist.kilometerstand = parse_int(request.form.get("kilometerstand"))
    checklist.anmerkungen = request.form.get("anmerkungen")

    ServiceChecklistItem.query.filter_by(checklist_id=checklist.id).delete()
    item_texts = request.form.getlist("item_text")
    item_comments = request.form.getlist("item_comment")
    rows = []
    for index, text in enumerate(item_texts):
        text = text.strip()
        comment = item_comments[index].strip() if index < len(item_comments) else ""
        if not text and not comment:
            continue
        rows.append((text or "Prüfpunkt", comment))

    for position, (text, comment) in enumerate(rows, start=1):
        db.session.add(
            ServiceChecklistItem(
                checklist_id=checklist.id,
                position=position,
                text=text or "Prüfpunkt",
                kommentar_vorlage=comment,
            )
        )


def create_checklist_record_from_template(template):
    record = ServiceChecklist(
        motorrad_id=template.motorrad_id,
        user_id=template.user_id,
        titel=request.form.get("titel") or template.titel,
        intervall_km=template.intervall_km,
        intervall_monate=template.intervall_monate,
        datum=parse_date(request.form.get("datum")) or date.today(),
        kilometerstand=parse_int(request.form.get("kilometerstand")),
        anmerkungen=request.form.get("anmerkungen"),
        is_template=False,
        source_template_id=template.id,
        completed_at=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    completed_ids = set(request.form.getlist("erledigt"))
    for item in template.items:
        db.session.add(
            ServiceChecklistItem(
                checklist_id=record.id,
                position=item.position,
                text=item.text,
                kommentar_vorlage=item.kommentar_vorlage,
                erledigt=str(item.id) in completed_ids,
                anmerkung=request.form.get(f"anmerkung_{item.id}"),
            )
        )
    return record


def merge_technical_rows(rows):
    merged = {}
    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        key = name.lower()
        merged[key] = {
            "name": name,
            "wert": row.get("wert", "").strip(),
            "einheit": row.get("einheit", "").strip(),
            "kategorie": row.get("kategorie", "").strip() or "Allgemein",
            "quelle": row.get("quelle", "").strip(),
        }
    return merged.values()


def strip_unit_suffix(value, unit):
    """Entfernt eine (auch mehrfach) als eigenes Wort angehaengte Einheit.

    Aeltere Versionen des Datenblatts haben Wert und Einheit in einem Feld
    angezeigt, sodass beim Speichern "583 ccm" mit Einheit "ccm" entstand.
    "5-Gang" bleibt bei Einheit "g" unveraendert, weil kein Leerzeichen davor steht.
    """
    suffix = (unit or "").strip().lower()
    if not suffix:
        return value
    while value.lower().endswith(suffix):
        head = value[: -len(suffix)]
        if not head or not head[-1].isspace():
            break
        value = head.rstrip()
    return value


def save_technical_specs(motorcycle):
    rows = []
    names = request.form.getlist("name")
    values = request.form.getlist("wert")
    units = request.form.getlist("einheit")
    categories = request.form.getlist("kategorie")
    sources = request.form.getlist("quelle")

    for index, name in enumerate(names):
        name = name.strip()
        value = values[index].strip() if index < len(values) else ""
        unit = units[index].strip() if index < len(units) else ""
        value = strip_unit_suffix(value, unit)
        if not name or not value:
            continue
        rows.append(
            {
                "name": name,
                "wert": value,
                "einheit": unit,
                "kategorie": categories[index].strip() if index < len(categories) else "Allgemein",
                "quelle": sources[index].strip() if index < len(sources) else "",
            }
        )

    rows.extend(parse_technical_csv(request.files.get("csv_file")))

    merged_rows = list(merge_technical_rows(rows))
    if not merged_rows:
        return

    TechnicalSpec.query.filter_by(motorrad_id=motorcycle.id).delete()
    for index, row in enumerate(merged_rows):
        db.session.add(TechnicalSpec(motorrad_id=motorcycle.id, user_id=motorcycle.user_id, position=index, **row))
    db.session.commit()


def get_technical_context(motorcycle):
    specs = (
        TechnicalSpec.query.filter_by(motorrad_id=motorcycle.id)
        .order_by(TechnicalSpec.kategorie, TechnicalSpec.name)
        .all()
    )
    suggestion_names = {spec.name.lower() for spec in specs}
    suggestions = [
        {"kategorie": category, "name": name, "einheit": unit}
        for category, name, unit in TECHNICAL_SPEC_SUGGESTIONS
        if name.lower() not in suggestion_names
    ]
    return specs, suggestions


def create_checklist_record_from_payload(template, data):
    record = ServiceChecklist(
        motorrad_id=template.motorrad_id,
        user_id=template.user_id,
        titel=data.get("titel") or template.titel,
        intervall_km=template.intervall_km,
        intervall_monate=template.intervall_monate,
        datum=parse_date(data.get("datum")) or date.today(),
        kilometerstand=parse_int(data.get("kilometerstand")),
        anmerkungen=data.get("checklist_anmerkungen") or data.get("beschreibung"),
        is_template=False,
        source_template_id=template.id,
        completed_at=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    raw_completed = data.get("completed_item_ids", [])
    completed_ids = {str(item_id) for item_id in raw_completed} if isinstance(raw_completed, list) else set()
    item_notes = data.get("item_notes", {})
    if not isinstance(item_notes, dict):
        item_notes = {}
    for item in template.items:
        db.session.add(
            ServiceChecklistItem(
                checklist_id=record.id,
                position=item.position,
                text=item.text,
                kommentar_vorlage=item.kommentar_vorlage,
                erledigt=str(item.id) in completed_ids,
                anmerkung=item_notes.get(str(item.id)),
            )
        )
    return record


def serialize_service(service):
    return {
        "id": service.id,
        "motorrad_id": service.motorrad_id,
        "titel": service.titel,
        "datum": service.datum.isoformat() if service.datum else None,
        "kilometerstand": service.kilometerstand,
        "beschreibung": service.beschreibung,
        "kosten": service.kosten,
        "kategorie": service.kategorie,
        "updated_at": service.updated_at.isoformat(),
    }


def get_backup_path():
    setting = db.session.get(AppSetting, "backup_path")
    return setting.value if setting and setting.value else BACKUP_PATH_PLACEHOLDER


def get_disk_usage():
    try:
        usage = shutil.disk_usage(current_app.instance_path)
    except OSError:
        return None

    percent_used = round((usage.used / usage.total) * 100) if usage.total else 0
    return {
        "path": current_app.instance_path,
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent_used": min(percent_used, 100),
        "percent_free": max(100 - percent_used, 0),
    }


BACKUP_PATH_PLACEHOLDER = "/PFAD/ZUM/SICHERUNGSORDNER"


class BackupError(RuntimeError):
    """Backup konnte nicht erstellt werden (Konfiguration oder Dateisystem)."""


def create_server_backup():
    """Server-seitiges Backup in den konfigurierten Sicherungsordner (nur Admin).

    Die SQLite-Datei wird ueber die Backup-API kopiert, damit auch bei laufenden
    Schreibzugriffen eine konsistente Kopie entsteht; der Upload-Ordner wird
    als Ganzes kopiert.
    """
    backup_path = get_backup_path()
    if not backup_path or backup_path == BACKUP_PATH_PLACEHOLDER:
        raise BackupError("Bitte zuerst einen Sicherungsort eintragen.")

    backup_root = Path(backup_path).expanduser()
    timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
    target = backup_root / f"motorrad_service_backup_{timestamp}"
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise BackupError("Es läuft bereits ein Backup in dieser Sekunde. Bitte kurz warten.") from error
    except OSError as error:
        raise BackupError(f"Sicherungsort nicht beschreibbar: {backup_root}") from error

    try:
        if db.engine.dialect.name == "sqlite":
            import sqlite3

            raw_connection = db.engine.raw_connection()
            try:
                with sqlite3.connect(target / "motorcycle_service.sqlite3") as destination:
                    raw_connection.driver_connection.backup(destination)
            finally:
                raw_connection.close()

        uploads_path = Path(current_app.config["UPLOAD_FOLDER"])
        if uploads_path.exists():
            shutil.copytree(uploads_path, target / "uploads", dirs_exist_ok=True)
    except OSError as error:
        raise BackupError(f"Backup fehlgeschlagen: {error}") from error

    return target
