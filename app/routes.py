from datetime import date, datetime
from pathlib import Path
import shutil

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    send_from_directory,
    url_for,
)
from flask_login import login_required, current_user

from app import db
from app.auth import admin_required
from app.models import (
    AppSetting,
    Motorcycle,
    ServiceChecklist,
    ServiceChecklistItem,
    ServiceEntry,
    TechnicalSpec,
)
from app.utils import (
    CATEGORIES,
    SERVICE_CHECKLIST_PRESETS,
    TECHNICAL_SPEC_SUGGESTIONS,
    parse_date,
    parse_checklist_csv,
    parse_int,
    parse_technical_csv,
    parse_technical_import,
    save_upload,
)


bp = Blueprint("main", __name__)


def require_motorcycle_ownership(motorcycle_id):
    """Verify current user owns the motorcycle."""
    motorcycle = Motorcycle.query.get_or_404(motorcycle_id)
    if not current_user.is_admin and motorcycle.user_id != current_user.id:
        abort(403)
    return motorcycle


DEFAULT_CHECKLIST_CSV = "\n".join(
    [
        "Motorrad;Titel;km;Intervall;Position;Pruefpunkt;Kommentar",
        "BMW R 1250 GS;Jahresservice;10000;12;1;Oelstand pruefen;Motor warmfahren und auf ebenem Untergrund pruefen",
        "BMW R 1250 GS;Jahresservice;10000;12;2;Bremsbelaege pruefen;Vorne und hinten Sichtpruefung durchfuehren",
        "BMW R 1250 GS;Jahresservice;10000;12;3;Reifendruck pruefen;Herstellerangaben beachten",
    ]
)


@bp.app_context_processor
def inject_settings():
    return {"backup_path": get_backup_path()}


@bp.app_template_filter("number")
def number_filter(value):
    if value in (None, ""):
        return "-"
    return f"{int(value):,}".replace(",", ".")


@bp.app_template_filter("date_de")
def date_filter(value):
    if not value:
        return "-"
    return value.strftime("%d.%m.%Y")


@bp.route("/")
@login_required
def index():
    query = Motorcycle.query if current_user.is_admin else Motorcycle.query.filter_by(user_id=current_user.id)
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "marke")

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Motorcycle.marke.ilike(like), Motorcycle.modell.ilike(like))
        )

    if sort == "baujahr":
        query = query.order_by(Motorcycle.baujahr.desc().nullslast())
    elif sort == "kilometerstand":
        query = query.order_by(Motorcycle.kilometerstand.desc().nullslast())
    else:
        query = query.order_by(Motorcycle.marke, Motorcycle.modell)

    motorcycles = query.all()
    active_motorcycles = [motorcycle for motorcycle in motorcycles if motorcycle.aktiv]
    garage_total_km = sum(motorcycle.kilometerstand or 0 for motorcycle in motorcycles)
    return render_template(
        "motorcycles/index.html",
        motorcycles=motorcycles,
        active_motorcycles=active_motorcycles,
        garage_total_km=garage_total_km,
        search=search,
        sort=sort,
    )


@bp.route("/settings/backup-path", methods=["POST"])
@login_required
@admin_required
def backup_path_update():
    setting = AppSetting.query.get("backup_path")
    if not setting:
        setting = AppSetting(key="backup_path")
        db.session.add(setting)
    setting.value = request.form.get("backup_path", "").strip() or "/PFAD/ZUM/SICHERUNGSORDNER"
    db.session.commit()
    return redirect(request.referrer or url_for("main.index"))


@bp.route("/einstellungen")
@login_required
def settings():
    return render_template("settings.html")


@bp.route("/checklisten/neu", methods=["GET", "POST"])
@login_required
def checklist_new_global():
    motorcycles = (
        Motorcycle.query if current_user.is_admin
        else Motorcycle.query.filter_by(user_id=current_user.id)
    ).order_by(Motorcycle.marke, Motorcycle.modell).all()
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

    selected_id = parse_int(request.args.get("motorrad_id"))
    selected_motorcycle = Motorcycle.query.get(selected_id) if selected_id else (motorcycles[0] if motorcycles else None)
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


@bp.route("/checklisten/csv-vorlage")
@login_required
def checklist_csv_template():
    return Response(
        DEFAULT_CHECKLIST_CSV + "\n",
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=checklisten_vorlage.csv"},
    )


@bp.route("/technik", methods=["GET", "POST"])
@login_required
def technical_data_global():
    motorcycles = (
        Motorcycle.query if current_user.is_admin
        else Motorcycle.query.filter_by(user_id=current_user.id)
    ).order_by(Motorcycle.marke, Motorcycle.modell).all()
    selected_id = parse_int(request.values.get("motorrad_id"))
    motorcycle = Motorcycle.query.get(selected_id) if selected_id else (motorcycles[0] if motorcycles else None)

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
def technical_csv_template():
    csv_text = "\n".join(
        [
            "Kategorie;Eintrag;Wert;Einheit;Quelle",
            "Motor;Hubraum;583;ccm;Fahrzeugschein",
            "Motor;Leistung;50;PS;Fahrzeugschein",
            "Motor;Drehmoment;53;Nm;Werkstatthandbuch",
            "Antrieb;Getriebe;5-Gang;;Werkstatthandbuch",
            "Reifen;Reifen vorne;90/90-21;;Handbuch",
            "Reifen;Reifen hinten;130/80-17;;Handbuch",
        ]
    )
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=technische_daten_vorlage.csv"},
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
        image_path, _ = save_upload(request.files.get("bild"), motorcycle.id, "images")
        if image_path:
            motorcycle.bild = image_path
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))
    return render_template("motorcycles/form.html", motorcycle=motorcycle, title="Motorrad anlegen")


@bp.route("/motorrad/<int:motorrad_id>")
@login_required
def motorcycle_detail(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    ensure_motorcycle_mileage_is_current(motorcycle)
    owner_filter = {} if current_user.is_admin else {"user_id": current_user.id}
    services = (
        ServiceEntry.query.filter_by(motorrad_id=motorrad_id, **owner_filter)
        .order_by(ServiceEntry.datum.desc(), ServiceEntry.id.desc())
        .all()
    )
    costs_by_category = {}
    for entry in services:
        costs_by_category[entry.kategorie] = costs_by_category.get(entry.kategorie, 0) + (entry.kosten or 0)
    total_costs = sum(costs_by_category.values())
    technical_specs = (
        TechnicalSpec.query.filter_by(motorrad_id=motorrad_id, **owner_filter)
        .order_by(TechnicalSpec.kategorie, TechnicalSpec.name)
        .all()
    )
    checklist_templates = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, is_template=True, **owner_filter)
        .order_by(ServiceChecklist.datum.desc().nullslast(), ServiceChecklist.id.desc())
        .limit(5)
        .all()
    )
    checklist_records = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, is_template=False, **owner_filter)
        .order_by(ServiceChecklist.completed_at.desc().nullslast(), ServiceChecklist.id.desc())
        .limit(5)
        .all()
    )
    checklist_records = unique_checklist_records(checklist_records)
    return render_template(
        "motorcycles/detail.html",
        motorcycle=motorcycle,
        services=services,
        costs_by_category=costs_by_category,
        total_costs=total_costs,
        technical_specs=technical_specs,
        checklist_templates=checklist_templates,
        checklist_records=checklist_records,
    )


@bp.route("/motorrad/<int:motorrad_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def motorcycle_edit(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    ensure_motorcycle_mileage_is_current(motorcycle)
    if request.method == "POST":
        fill_motorcycle(motorcycle)
        image_path, _ = save_upload(request.files.get("bild"), motorcycle.id, "images")
        if image_path:
            delete_upload_file(motorcycle.bild)
            motorcycle.bild = image_path
        db.session.commit()
        return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))
    return render_template("motorcycles/form.html", motorcycle=motorcycle, title="Motorrad bearbeiten")


@bp.route("/motorrad/<int:motorrad_id>/bild-loeschen", methods=["POST"])
@login_required
def motorcycle_image_delete(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    delete_upload_file(motorcycle.bild)
    motorcycle.bild = None
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
        motorcycles=(
            Motorcycle.query if current_user.is_admin
            else Motorcycle.query.filter_by(user_id=current_user.id)
        ).order_by(Motorcycle.marke, Motorcycle.modell).all(),
        specs=specs,
        suggestions=suggestions,
    )


@bp.route("/motorrad/<int:motorrad_id>/datenblatt", methods=["POST"])
@login_required
def motorcycle_data_sheet_update(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    save_technical_specs(motorcycle)
    return redirect(url_for("main.motorcycle_detail", motorrad_id=motorcycle.id))


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
    checklist_records = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id)
        .filter_by(is_template=False)
        .order_by(ServiceChecklist.completed_at.desc().nullslast(), ServiceChecklist.id.desc())
        .all()
    )
    return render_template(
        "checklists/index.html",
        motorcycle=motorcycle,
        checklist_templates=checklist_templates,
        checklist_records=checklist_records,
    )


@bp.route("/motorrad/<int:motorrad_id>/checklisten/neu", methods=["GET", "POST"])
@login_required
def checklist_new(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    preset_key = request.values.get("preset", "")
    preset = SERVICE_CHECKLIST_PRESETS.get(preset_key, {})

    if request.method == "POST":
        imported = create_checklists_from_csv(request.files.get("csv_file"))
        if imported:
            db.session.commit()
            return redirect(url_for("main.checklist_index", motorrad_id=motorcycle.id))

        checklist = create_checklist_from_form(motorcycle)
        db.session.commit()
        return redirect(url_for("main.checklist_index", motorrad_id=checklist.motorrad_id))

    return render_template(
        "checklists/form.html",
        motorcycle=motorcycle,
        motorcycles=(
            Motorcycle.query if current_user.is_admin
            else Motorcycle.query.filter_by(user_id=current_user.id)
        ).order_by(Motorcycle.marke, Motorcycle.modell).all(),
        preset_key=preset_key,
        preset=preset,
        presets=SERVICE_CHECKLIST_PRESETS,
    )


@bp.route("/checklisten/<int:checklist_id>", methods=["GET", "POST"])
@login_required
def checklist_edit(checklist_id):
    checklist = ServiceChecklist.query.get_or_404(checklist_id)
    require_motorcycle_ownership(checklist.motorrad_id)
    if request.method == "POST":
        if not checklist.is_template:
            abort(409)
        record = create_checklist_record_from_template(checklist)
        db.session.commit()
        return redirect(url_for("main.checklist_edit", checklist_id=record.id))

    return render_template("checklists/edit.html", checklist=checklist, motorcycle=checklist.motorcycle)


@bp.route("/checklisten/<int:checklist_id>/loeschen", methods=["POST"])
@login_required
def checklist_delete(checklist_id):
    checklist = ServiceChecklist.query.get_or_404(checklist_id)
    require_motorcycle_ownership(checklist.motorrad_id)
    motorrad_id = checklist.motorrad_id
    db.session.delete(checklist)
    db.session.commit()
    return redirect(url_for("main.checklist_index", motorrad_id=motorrad_id))


@bp.route("/motorrad/<int:motorrad_id>/service/neu", methods=["GET", "POST"])
@login_required
def service_new(motorrad_id):
    motorcycle = require_motorcycle_ownership(motorrad_id)
    service = ServiceEntry(motorrad_id=motorrad_id, datum=date.today(), user_id=current_user.id)
    checklist_templates = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, user_id=current_user.id, is_template=True)
        .order_by(ServiceChecklist.titel)
        .all()
    )
    if request.method == "POST":
        fill_service(service)
        db.session.add(service)
        db.session.flush()
        receipt_path, original_name = save_upload(request.files.get("beleg"), motorrad_id, "receipts")
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
        title="Service eintragen",
    )


@bp.route("/service/<int:service_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def service_edit(service_id):
    service = ServiceEntry.query.get_or_404(service_id)
    if service.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    motorcycle = service.motorcycle
    if request.method == "POST":
        fill_service(service)
        receipt_path, original_name = save_upload(request.files.get("beleg"), service.motorrad_id, "receipts")
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


@bp.route("/service/<int:service_id>/loeschen", methods=["POST"])
@login_required
def service_delete(service_id):
    service = ServiceEntry.query.get_or_404(service_id)
    if service.user_id != current_user.id and not current_user.is_admin:
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

    motorcycles = (
        Motorcycle.query if current_user.is_admin
        else Motorcycle.query.filter_by(user_id=current_user.id)
    ).order_by(Motorcycle.marke, Motorcycle.modell).all()
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

    motorcycle = Motorcycle.query.get_or_404(motorrad_id)
    if not current_user.is_admin and motorcycle.user_id != current_user.id:
        abort(403)

    owner_filter = {} if current_user.is_admin else {"user_id": current_user.id}
    services = ServiceEntry.query.filter_by(motorrad_id=motorrad_id, **owner_filter).order_by(ServiceEntry.datum.desc()).all()
    return jsonify([serialize_service(s) for s in services])


@bp.route("/api/services", methods=["POST"])
def api_create_service():
    if not current_user.is_authenticated:
        abort(401)

    data = request.get_json(force=True)
    motorcycle = Motorcycle.query.get_or_404(data.get("motorrad_id"))
    if not current_user.is_admin and motorcycle.user_id != current_user.id:
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
    if not current_user.is_authenticated:
        abort(401)

    data = request.get_json(force=True)
    create_sync_backup()
    created = []
    for item in data.get("services", []):
        motorcycle = Motorcycle.query.get(item.get("motorrad_id"))
        if not motorcycle or (not current_user.is_admin and motorcycle.user_id != current_user.id):
            continue
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
        db.session.add(service)
        db.session.flush()
        refresh_motorcycle_mileage(motorcycle)
        created.append(serialize_service(service))
    checklist_services = []
    for item in data.get("checklist_services", []):
        template = ServiceChecklist.query.get(item.get("checklist_id"))
        motorcycle = Motorcycle.query.get(item.get("motorrad_id"))
        if not template or not motorcycle or template.motorrad_id != motorcycle.id:
            continue
        if not current_user.is_admin and motorcycle.user_id != current_user.id:
            continue
        service = ServiceEntry(
            motorrad_id=motorcycle.id,
            user_id=current_user.id,
            titel=item.get("titel") or template.titel,
            datum=parse_date(item.get("datum")) or date.today(),
            kilometerstand=parse_int(item.get("kilometerstand")),
            beschreibung=item.get("beschreibung"),
            kosten=parse_int(item.get("kosten")),
            kategorie=item.get("kategorie") or "Wartung / Service",
            naechster_service_km=parse_int(item.get("naechster_service_km")),
            naechster_service_datum=parse_date(item.get("naechster_service_datum")),
        )
        db.session.add(service)
        db.session.flush()
        record = create_checklist_record_from_payload(template, item)
        refresh_motorcycle_mileage(motorcycle)
        checklist_services.append(
            {"service": serialize_service(service), "checklist_id": record.id}
        )
    db.session.commit()
    return jsonify({"created": created, "checklist_services": checklist_services})


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
    motorcycle.aktiv = request.form.get("aktiv") == "on"
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
    motorcycle.kilometerstand = latest_service_mileage(motorcycle.id)


def ensure_motorcycle_mileage_is_current(motorcycle):
    latest_mileage = latest_service_mileage(motorcycle.id)
    if motorcycle.kilometerstand != latest_mileage:
        motorcycle.kilometerstand = latest_mileage
        db.session.commit()


def latest_service_mileage(motorrad_id):
    candidates = []
    services = (
        ServiceEntry.query.filter_by(motorrad_id=motorrad_id)
        .filter(ServiceEntry.kilometerstand.isnot(None))
        .all()
    )
    for service in services:
        candidates.append((service.datum or date.min, service.id, service.kilometerstand))

    checklist_records = (
        ServiceChecklist.query.filter_by(motorrad_id=motorrad_id, is_template=False)
        .all()
    )
    for checklist in checklist_records:
        mileage = checklist.kilometerstand or checklist.intervall_km
        if not mileage:
            continue
        checklist_date = checklist.datum or (checklist.completed_at.date() if checklist.completed_at else date.min)
        candidates.append((checklist_date, checklist.id, mileage))

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


def split_lines(text):
    return [line.strip().strip("-") for line in (text or "").splitlines() if line.strip().strip("-")]


def find_motorcycle_for_checklist_row(row):
    motorrad_id = parse_int(row.get("motorrad_id"))
    if motorrad_id:
        motorcycle = Motorcycle.query.get(motorrad_id)
        if motorcycle and current_user.is_authenticated and not current_user.is_admin:
            return motorcycle if motorcycle.user_id == current_user.id else None
        return motorcycle

    label = (row.get("motorrad") or "").strip().lower()
    if not label:
        return None
    query = Motorcycle.query
    if current_user.is_authenticated and not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    motorcycles = query.all()
    for motorcycle in motorcycles:
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
        key = (motorcycle.id, row["titel"])
        grouped.setdefault(
            key,
            {
                "motorcycle": motorcycle,
                "titel": row["titel"],
                "intervall_km": parse_int(row.get("intervall_km")),
                "intervall_monate": parse_int(row.get("intervall_monate")),
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
        completed_at=datetime.utcnow(),
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
        if not name or not value:
            continue
        rows.append(
            {
                "name": name,
                "wert": value,
                "einheit": units[index].strip() if index < len(units) else "",
                "kategorie": categories[index].strip() if index < len(categories) else "Allgemein",
                "quelle": sources[index].strip() if index < len(sources) else "",
            }
        )

    rows.extend(parse_technical_import(request.form.get("import_text")))
    rows.extend(parse_technical_csv(request.files.get("csv_file")))

    merged_rows = list(merge_technical_rows(rows))
    if not merged_rows:
        return

    TechnicalSpec.query.filter_by(motorrad_id=motorcycle.id).delete()
    for row in merged_rows:
        db.session.add(TechnicalSpec(motorrad_id=motorcycle.id, user_id=motorcycle.user_id, **row))
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
        completed_at=datetime.utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    completed_ids = {str(item_id) for item_id in data.get("completed_item_ids", [])}
    item_notes = data.get("item_notes", {})
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
    setting = AppSetting.query.get("backup_path")
    return setting.value if setting and setting.value else "/PFAD/ZUM/SICHERUNGSORDNER"


def create_sync_backup():
    backup_path = get_backup_path()
    if not backup_path or backup_path == "/PFAD/ZUM/SICHERUNGSORDNER":
        return None

    backup_root = Path(backup_path).expanduser()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target = backup_root / f"motorrad_service_sync_{timestamp}"
    target.mkdir(parents=True, exist_ok=True)

    db_path = Path(current_app.instance_path) / "motorcycle_service.sqlite3"
    if db_path.exists():
        shutil.copy2(db_path, target / "motorcycle_service.sqlite3")

    uploads_path = Path(current_app.config["UPLOAD_FOLDER"])
    if uploads_path.exists():
        shutil.copytree(uploads_path, target / "uploads", dirs_exist_ok=True)

    return target
