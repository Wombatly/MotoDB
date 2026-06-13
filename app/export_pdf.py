"""Erzeugt eine lesbare PDF-Zusammenfassung je Motorrad für den Export."""

from datetime import date

from fpdf import FPDF

INK = (24, 26, 29)
MUTED = (110, 110, 110)
ACCENT = (201, 110, 38)


def _s(value):
    """Macht einen Wert latin-1-sicher (Kernschriften von fpdf2 können kein UTF-8)."""
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "€": "EUR", "·": "-", "–": "-", "—": "-", "…": "...",
        "„": '"', "“": '"', "”": '"', "‚": "'", "‘": "'", "’": "'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _int(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _km(value):
    return f"{_int(value)} km" if value not in (None, "") else ""


def _eur(value):
    if value in (None, ""):
        return ""
    try:
        formatted = f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return ""
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} EUR"


def _date(value):
    return value.strftime("%d.%m.%Y") if value else ""


def _interval(checklist):
    parts = []
    if checklist.intervall_km:
        parts.append(f"alle {_int(checklist.intervall_km)} km")
    if checklist.intervall_monate:
        parts.append(f"alle {_int(checklist.intervall_monate)} Monate")
    return " / ".join(parts)


class _SummaryPDF(FPDF):
    title_text = ""

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, _s(self.title_text), align="R", new_x="LMARGIN", new_y="NEXT")

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"Seite {self.page_no()}", align="C")


def build_motorcycle_pdf(motorcycle, services, specs, checklists, documents, title_image_path=None):
    pdf = _SummaryPDF(format="A4", unit="mm")
    pdf.title_text = f"{motorcycle.marke} {motorcycle.modell}"
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    width = pdf.epw

    def heading(text):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*INK)
        pdf.cell(0, 8, _s(text), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.5)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + width, y)
        pdf.ln(2)

    def kv(label, value):
        value = _s(value)
        if not value:
            return
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(48, 6, _s(label), new_x="RIGHT", new_y="TOP")
        pdf.set_text_color(*INK)
        pdf.multi_cell(width - 48, 6, value, new_x="LMARGIN", new_y="NEXT")

    def para(text, size=10, style="", color=INK):
        text = _s(text)
        if not text:
            return
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    def fit(text, max_w, size):
        text = _s(text)
        pdf.set_font("Helvetica", "", size)
        if pdf.get_string_width(text) <= max_w:
            return text
        while text and pdf.get_string_width(f"{text}...") > max_w:
            text = text[:-1]
        return f"{text}..."

    def spec_grid(pairs, columns=2):
        gutter = 6
        col_w = (width - gutter * (columns - 1)) / columns
        name_w = col_w * 0.62
        value_w = col_w - name_w
        row_h = 6
        for start in range(0, len(pairs), columns):
            chunk = pairs[start:start + columns]
            if pdf.will_page_break(row_h):
                pdf.add_page()
            y = pdf.get_y()
            for col, (label, value) in enumerate(chunk):
                x = pdf.l_margin + col * (col_w + gutter)
                pdf.set_xy(x, y)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MUTED)
                pdf.cell(name_w, row_h, fit(label, name_w - 2, 9), new_x="RIGHT", new_y="TOP")
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*INK)
                pdf.cell(value_w, row_h, fit(value, value_w - 1, 9), align="R", new_x="LMARGIN", new_y="TOP")
            pdf.set_y(y + row_h)

    # Titelblock
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*INK)
    pdf.cell(0, 12, _s(f"{motorcycle.marke} {motorcycle.modell}"), new_x="LMARGIN", new_y="NEXT")
    subtitle = " / ".join(
        part for part in [
            str(motorcycle.baujahr) if motorcycle.baujahr else "",
            _km(motorcycle.kilometerstand),
            _s(motorcycle.kennzeichen) if motorcycle.kennzeichen else "",
        ] if part
    )
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 7, _s(subtitle), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, _s(f"Erstellt am {date.today().strftime('%d.%m.%Y')}"), new_x="LMARGIN", new_y="NEXT")

    if title_image_path:
        try:
            pdf.ln(3)
            box_w, box_h = 110, 70
            pdf.image(
                title_image_path,
                x=pdf.l_margin + (width - box_w) / 2,
                w=box_w,
                h=box_h,
                keep_aspect_ratio=True,
            )
            pdf.ln(2)
        except Exception:
            pass

    # Seite 1: fahrzeugspezifische Daten
    heading("Fahrzeugdaten")
    kv("Marke", motorcycle.marke)
    kv("Modell", motorcycle.modell)
    kv("Baujahr", motorcycle.baujahr)
    kv("Erstzulassung", _date(motorcycle.erstzulassung))
    kv("Kennzeichen", motorcycle.kennzeichen)
    kv("Fahrgestellnr. (VIN)", motorcycle.vin)
    kv("Farbe", motorcycle.farbe)
    kv("Hubraum", f"{_int(motorcycle.hubraum)} ccm" if motorcycle.hubraum else "")
    kv("Leistung", f"{_int(motorcycle.ps)} PS" if motorcycle.ps else "")
    kv("Kilometerstand", _km(motorcycle.kilometerstand))
    kv("Kaufdatum", _date(motorcycle.kaufdatum))
    kv("Kaufpreis", _eur(motorcycle.kaufpreis))
    if motorcycle.verkauft_am:
        kv("Verkauft am", _date(motorcycle.verkauft_am))
        kv("Verkaufspreis", _eur(motorcycle.verkaufspreis))
    kv("Status", "Aktiv" if motorcycle.aktiv else "Inaktiv")
    if motorcycle.notizen:
        pdf.ln(1)
        para("Notizen", style="B")
        para(motorcycle.notizen)

    # Kostenübersicht
    total = sum((service.kosten or 0) for service in services)
    by_category = {}
    for service in services:
        key = service.kategorie or "Sonstiges"
        by_category[key] = by_category.get(key, 0) + (service.kosten or 0)
    heading("Kostenübersicht")
    kv("Service-Einträge", str(len(services)))
    kv("Kosten gesamt", _eur(total))
    for category, amount in sorted(by_category.items()):
        if amount:
            kv(f"  {category}", _eur(amount))

    # Seite 2: allgemeine technische Daten des Motorradtyps (mehrspaltig, volle Breite)
    pdf.add_page()
    heading("Technische Daten")
    if specs:
        grouped = {}
        order = []
        for spec in specs:
            category = spec.kategorie or "Allgemein"
            if category not in grouped:
                grouped[category] = []
                order.append(category)
            value = _s(spec.wert)
            if spec.einheit:
                value = f"{value} {_s(spec.einheit)}".strip()
            grouped[category].append((spec.name, value))
        for category in order:
            para(category, style="B", size=11)
            spec_grid(grouped[category], columns=2)
            pdf.ln(2)
    else:
        para("Keine technischen Daten erfasst.", color=MUTED)

    # Seite 3: durchgeführte Servicechecks
    pdf.add_page()
    heading("Service-Historie")
    if services:
        for service in services:
            title = " - ".join(part for part in [_date(service.datum), _s(service.titel or "Service")] if part)
            para(title, style="B", size=10)
            meta = " | ".join(
                part for part in [_km(service.kilometerstand), _eur(service.kosten), _s(service.kategorie or "")] if part
            )
            para(meta, size=9, color=MUTED)
            if service.beschreibung:
                para(service.beschreibung, size=9)
            next_service = " / ".join(
                part for part in [
                    _km(service.naechster_service_km) if service.naechster_service_km else "",
                    _date(service.naechster_service_datum) if service.naechster_service_datum else "",
                ] if part
            )
            if next_service:
                para(f"Naechster Service: {next_service}", size=9, color=MUTED)
            pdf.ln(1)
    else:
        para("Keine Service-Eintraege erfasst.", color=MUTED)

    # Checklisten
    records = [checklist for checklist in checklists if not checklist.is_template]
    templates = [checklist for checklist in checklists if checklist.is_template]
    if records or templates:
        heading("Checklisten")
    if records:
        para("Ausgefuellte Checklisten", style="B", size=11)
        for record in records:
            when = _date(record.datum or (record.completed_at.date() if record.completed_at else None))
            head = " - ".join(part for part in [when, _s(record.titel)] if part)
            if record.kilometerstand:
                head = f"{head}  ({_km(record.kilometerstand)})"
            para(head, style="B", size=10)
            for item in record.items:
                box = "[x]" if item.erledigt else "[ ]"
                para(f"  {box} {_s(item.text)}", size=9)
                if item.anmerkung:
                    para(f"      {_s(item.anmerkung)}", size=9, color=MUTED)
            if record.anmerkungen:
                para(f"  Anmerkung: {_s(record.anmerkungen)}", size=9, color=MUTED)
            pdf.ln(1)
    if templates:
        para("Vorlagen", style="B", size=11)
        for template in templates:
            interval = _interval(template)
            suffix = f" ({interval})" if interval else ""
            para(f"  - {_s(template.titel)}{suffix} - {len(template.items)} Pruefpunkte", size=9)

    # Dokumente (nur als Verweis auf die Dateien im Ordner)
    if documents:
        heading("Dokumente")
        para('Die Dateien liegen im Ordner "dokumente/".', size=9, color=MUTED)
        for document in documents:
            label = " - ".join(part for part in [_s(document.titel), _s(document.kategorie)] if part)
            filename = _s(document.original_name or "")
            suffix = f"  ({filename})" if filename else ""
            para(f"  - {label}{suffix}", size=9)

    return bytes(pdf.output())
