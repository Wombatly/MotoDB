from datetime import datetime
from app.timeutils import utcnow
import csv
import io
import json
from pathlib import Path
import re
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

if Image is not None:
    Image.MAX_IMAGE_PIXELS = 24_000_000

ALLOWED_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PDF_EXTENSION = ".pdf"
MAX_CHECKLIST_ITEM_FILE_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_EXTRACTED_TEXT_CHARS = 100_000


CATEGORIES = [
    "Wartung / Service",
    "Ersatzteile",
    "Reifen",
    "Versicherung",
    "Steuer",
    "TÜV / HU",
    "Kraftstoff",
    "Zubehör",
    "Reparatur",
    "Sonstiges",
]


TECHNICAL_SPEC_SUGGESTIONS = [
    ("Motor", "Motorbauart", ""),
    ("Motor", "Hubraum", "ccm"),
    ("Motor", "Leistung", "PS"),
    ("Motor", "Drehmoment", "Nm"),
    ("Motor", "Verdichtung", ""),
    ("Motor", "Kühlung", ""),
    ("Motor", "Gemischaufbereitung", ""),
    ("Motor", "Zündung", ""),
    ("Motor", "Ölmenge", "l"),
    ("Motor", "Ölspezifikation", ""),
    ("Antrieb", "Getriebe", ""),
    ("Antrieb", "Endantrieb", ""),
    ("Antrieb", "Kette", ""),
    ("Antrieb", "Ritzel/Kettenrad", ""),
    ("Fahrwerk", "Rahmen", ""),
    ("Fahrwerk", "Vorderradfederung", ""),
    ("Fahrwerk", "Hinterradfederung", ""),
    ("Fahrwerk", "Federweg vorne", "mm"),
    ("Fahrwerk", "Federweg hinten", "mm"),
    ("Bremsen", "Bremse vorne", ""),
    ("Bremsen", "Bremse hinten", ""),
    ("Reifen", "Reifen vorne", ""),
    ("Reifen", "Reifen hinten", ""),
    ("Reifen", "Luftdruck vorne", "bar"),
    ("Reifen", "Luftdruck hinten", "bar"),
    ("Maße", "Radstand", "mm"),
    ("Maße", "Sitzhöhe", "mm"),
    ("Maße", "Leergewicht", "kg"),
    ("Maße", "Zulässiges Gesamtgewicht", "kg"),
    ("Maße", "Tankinhalt", "l"),
    ("Elektrik", "Batterie", ""),
    ("Elektrik", "Scheinwerfer", ""),
    ("Elektrik", "Sicherung", ""),
]


SERVICE_CHECKLIST_PRESETS = {
    "1000": {
        "titel": "1.000 km Einfahrkontrolle",
        "intervall_km": 1000,
        "intervall_monate": None,
        "items": [
            "Motoröl und Ölfilter prüfen/wechseln",
            "Kette prüfen, reinigen und schmieren",
            "Bremsanlage auf Dichtheit und Funktion prüfen",
            "Reifen und Luftdruck prüfen",
            "Schraubverbindungen sichtprüfen",
            "Probefahrt durchführen",
        ],
    },
    "10000": {
        "titel": "10.000 km Service",
        "intervall_km": 10000,
        "intervall_monate": 12,
        "items": [
            "Motoröl wechseln",
            "Ölfilter wechseln",
            "Luftfilter prüfen/ersetzen",
            "Zündkerzen prüfen/ersetzen",
            "Bremsbeläge und Bremsscheiben prüfen",
            "Bremsflüssigkeitsstand prüfen",
            "Kette reinigen, schmieren und Spannung prüfen",
            "Reifenprofil und Luftdruck prüfen",
            "Beleuchtung und Hupe prüfen",
            "Probefahrt durchführen",
        ],
    },
    "20000": {
        "titel": "20.000 km großer Service",
        "intervall_km": 20000,
        "intervall_monate": 24,
        "items": [
            "Motoröl und Ölfilter wechseln",
            "Luftfilter ersetzen",
            "Zündkerzen ersetzen",
            "Ventilspiel prüfen/einstellen",
            "Bremsflüssigkeit wechseln",
            "Kühlmittel prüfen/wechseln",
            "Antriebssatz prüfen",
            "Lenkkopflager prüfen",
            "Radlager prüfen",
            "Fahrwerk auf Dichtheit prüfen",
            "Probefahrt durchführen",
        ],
    },
    "season": {
        "titel": "Saisoncheck",
        "intervall_km": None,
        "intervall_monate": 12,
        "items": [
            "Batterie prüfen/laden",
            "Reifenalter, Profil und Luftdruck prüfen",
            "Bremsen prüfen",
            "Flüssigkeitsstände prüfen",
            "Beleuchtung prüfen",
            "Kette reinigen und schmieren",
            "Dokumente und HU-Termin prüfen",
        ],
    },
}


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_int(value):
    if value in (None, ""):
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return int(digits) if digits else None


def parse_technical_import(text):
    if not text:
        return []

    text = text.strip()
    parsed = []
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for name, value in data.items():
                parsed.append(
                    {
                        "name": str(name).strip(),
                        "wert": "" if value is None else str(value).strip(),
                        "einheit": "",
                        "kategorie": "Import",
                        "quelle": "",
                    }
                )
            return [row for row in parsed if row["name"]]
    except json.JSONDecodeError:
        pass

    for line in text.splitlines():
        line = line.strip().strip("-")
        if not line:
            continue
        if ":" in line:
            name, value = line.split(":", 1)
        elif "=" in line:
            name, value = line.split("=", 1)
        else:
            continue
        parsed.append(
            {
                "name": name.strip(),
                "wert": value.strip(),
                "einheit": "",
                "kategorie": "Import",
                "quelle": "",
            }
        )
    return [row for row in parsed if row["name"]]


def parse_technical_csv(file_storage):
    if not file_storage or not file_storage.filename:
        return []

    raw = file_storage.read()
    if not raw:
        return []

    text = raw.decode("utf-8-sig", errors="ignore")
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = []
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for line in reader:
        values = [value.strip() for value in line]
        if not values or not any(values):
            continue
        if values[0].lower() in {"kategorie", "category"}:
            continue
        values.extend([""] * (5 - len(values)))
        rows.append(
            {
                "kategorie": values[0] or "Import",
                "name": values[1],
                "wert": values[2],
                "einheit": values[3],
                "quelle": values[4],
            }
        )
    return [row for row in rows if row["name"]]


def parse_checklist_csv(file_storage):
    if not file_storage or not file_storage.filename:
        return []

    raw = file_storage.read()
    if not raw:
        return []

    text = raw.decode("utf-8-sig", errors="ignore")
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for line in reader:
        normalized = {
            (key or "").strip().lower().replace("_", "").replace("-", ""): (value or "").strip()
            for key, value in line.items()
        }
        raw_interval = (
            normalized.get("intervall")
            or normalized.get("interval")
            or normalized.get("wartungsintervall")
            or normalized.get("serviceintervall")
        )
        raw_km = (
            normalized.get("km")
            or normalized.get("intervallkm")
            or normalized.get("kilometer")
            or normalized.get("kilometerintervall")
        )
        raw_months = normalized.get("monate") or normalized.get("intervallmonate")
        intervall_km = raw_km
        intervall_monate = raw_months
        if raw_interval and raw_km and not raw_months:
            intervall_monate = raw_interval
        elif raw_interval and not raw_km and not raw_months:
            lowered_interval = raw_interval.lower()
            if "km" in lowered_interval or "kilometer" in lowered_interval:
                intervall_km = raw_interval
            elif "jahr" in lowered_interval:
                parsed_years = parse_int(raw_interval)
                intervall_monate = str(parsed_years * 12) if parsed_years else raw_interval
            else:
                intervall_monate = raw_interval

        title = (
            normalized.get("titel")
            or normalized.get("title")
            or normalized.get("checkliste")
            or normalized.get("service")
            or raw_interval
            or raw_km
            or "Service-Checkliste"
        )
        item_text = (
            normalized.get("pruefpunkt")
            or normalized.get("prüfpunkt")
            or normalized.get("punkt")
            or normalized.get("checkpunkt")
            or normalized.get("kontrollpunkt")
            or normalized.get("item")
            or normalized.get("aufgabe")
            or normalized.get("arbeit")
            or normalized.get("arbeiten")
            or normalized.get("taetigkeit")
            or normalized.get("tätigkeit")
            or normalized.get("beschreibung")
            or normalized.get("text")
            or normalized.get("name")
        )
        if not item_text:
            ignored_keys = {
                "motorrad",
                "motorcycle",
                "motorradid",
                "motorcycleid",
                "titel",
                "title",
                "checkliste",
                "service",
                "intervall",
                "interval",
                "wartungsintervall",
                "serviceintervall",
                "km",
                "intervallkm",
                "kilometer",
                "kilometerintervall",
                "monate",
                "intervallmonate",
                "position",
                "pos",
                "kommentar",
                "comment",
            }
            fallback_values = [
                value
                for key, value in normalized.items()
                if key not in ignored_keys and value
            ]
            item_text = fallback_values[0] if fallback_values else ""
        if not title or not item_text:
            continue
        rows.append(
            {
                "motorrad": normalized.get("motorrad") or normalized.get("motorcycle"),
                "motorrad_id": normalized.get("motorradid") or normalized.get("motorcycleid"),
                "titel": title,
                "intervall_km": intervall_km,
                "intervall_monate": intervall_monate,
                "position": normalized.get("position") or normalized.get("pos"),
                "text": item_text,
                "kommentar": normalized.get("kommentar") or normalized.get("comment"),
            }
        )
    return rows


def parse_checklist_item_file(file_storage):
    if not file_storage or not file_storage.filename:
        return []

    raw = file_storage.read(MAX_CHECKLIST_ITEM_FILE_BYTES + 1)
    if not raw:
        return []
    if len(raw) > MAX_CHECKLIST_ITEM_FILE_BYTES:
        return []

    extension = Path(file_storage.filename).suffix.lower()
    if extension == PDF_EXTENSION:
        text = extract_pdf_text(raw)
    else:
        text = raw.decode("utf-8-sig", errors="ignore")

    if not text.strip():
        return []
    return parse_checklist_item_text(text, extension)


def extract_pdf_text(raw):
    if not raw.startswith(b"%PDF-"):
        return ""

    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
    except Exception:
        return ""

    if getattr(reader, "is_encrypted", False):
        return ""

    page_text = []
    try:
        page_count = len(reader.pages)
    except Exception:
        return ""
    if page_count > MAX_PDF_PAGES:
        return ""

    extracted_chars = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        remaining = MAX_EXTRACTED_TEXT_CHARS - extracted_chars
        if remaining <= 0:
            break
        page_text.append(text[:remaining])
        extracted_chars += len(page_text[-1])
    return "\n".join(page_text)


def parse_checklist_item_text(text, extension=""):
    if extension == ".csv":
        rows = parse_checklist_item_csv(text)
        if rows:
            return rows

    rows = []
    for line in text.splitlines():
        point = clean_checklist_item_line(line)
        if point:
            rows.append((point, ""))
    return rows


def parse_checklist_item_csv(text):
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    raw_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    raw_rows = [[cell.strip() for cell in row] for row in raw_rows if any(cell.strip() for cell in row)]
    if not raw_rows:
        return []

    header_keys = {
        cell.lower().replace("_", "").replace("-", "")
        for cell in raw_rows[0]
    }
    known_headers = {
        "pruefpunkt",
        "prüfpunkt",
        "punkt",
        "checkpunkt",
        "kontrollpunkt",
        "aufgabe",
        "arbeit",
        "arbeiten",
        "taetigkeit",
        "tätigkeit",
        "beschreibung",
        "text",
        "name",
        "kommentar",
        "comment",
    }
    if header_keys & known_headers:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = []
        for line in reader:
            normalized = {
                (key or "").strip().lower().replace("_", "").replace("-", ""): (value or "").strip()
                for key, value in line.items()
            }
            point = (
                normalized.get("pruefpunkt")
                or normalized.get("prüfpunkt")
                or normalized.get("punkt")
                or normalized.get("checkpunkt")
                or normalized.get("kontrollpunkt")
                or normalized.get("aufgabe")
                or normalized.get("arbeit")
                or normalized.get("arbeiten")
                or normalized.get("taetigkeit")
                or normalized.get("tätigkeit")
                or normalized.get("beschreibung")
                or normalized.get("text")
                or normalized.get("name")
            )
            comment = normalized.get("kommentar") or normalized.get("comment") or ""
            point = clean_checklist_item_line(point or "")
            if point or comment:
                rows.append((point or "Prüfpunkt", comment))
        return rows

    rows = []
    for row in raw_rows:
        point = clean_checklist_item_line(row[0] if row else "")
        comment = row[1] if len(row) > 1 else ""
        if point or comment:
            rows.append((point or "Prüfpunkt", comment))
    return rows


def clean_checklist_item_line(line):
    value = (line or "").strip()
    value = re.sub(r"^\s*(?:[-*•]+|\[[ xX]\]|\d+[\.)])\s*", "", value)
    return value.strip()


def save_upload(file_storage, motorcycle_id, folder):
    if not file_storage or not file_storage.filename:
        return None, None

    original_name = secure_filename(file_storage.filename)
    if not original_name:
        return None, None

    extension = Path(original_name).suffix.lower()
    allowed_extensions = {
        "images": IMAGE_EXTENSIONS,
        "receipts": IMAGE_EXTENSIONS | {PDF_EXTENSION},
        "documents": IMAGE_EXTENSIONS | {PDF_EXTENSION},
    }
    if extension not in allowed_extensions.get(folder, set()):
        return None, None

    stored_extension = ".jpg" if extension in IMAGE_EXTENSIONS else extension
    filename = f"{utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{stored_extension}"
    relative_path = Path(str(motorcycle_id)) / folder / filename
    target = current_app.config["UPLOAD_FOLDER"] / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f".{target.name}.tmp")

    try:
        file_storage.save(temp_path)
        if extension in IMAGE_EXTENSIONS:
            if Image is None:
                return None, None
            optimize_image(temp_path, target)
        elif extension == PDF_EXTENSION:
            if not validate_pdf_file(temp_path):
                return None, None
            temp_path.replace(target)
        else:
            return None, None
    except Exception:
        target.unlink(missing_ok=True)
        return None, None
    finally:
        temp_path.unlink(missing_ok=True)

    return str(relative_path), original_name


def validate_pdf_file(path):
    try:
        with open(path, "rb") as uploaded_file:
            return uploaded_file.read(5) == b"%PDF-"
    except OSError:
        return False


def optimize_image(source_path, target_path, max_size=(1600, 1200), quality=82):
    if Image is None:
        return

    with Image.open(source_path, formats=ALLOWED_IMAGE_FORMATS) as image:
        if image.format not in ALLOWED_IMAGE_FORMATS:
            raise ValueError("Unsupported image format")
        image.verify()

    with Image.open(source_path, formats=ALLOWED_IMAGE_FORMATS) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(max_size)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(target_path, format="JPEG", quality=quality, optimize=True, progressive=True)
