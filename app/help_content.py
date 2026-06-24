"""Zentrale Hilfetexte für MotoDB.

Eine Quelle für die kontextsensitive Hilfe (``?``-Button im Seitenkopf, über
``page_header(..., help_key="...")``) und die Übersichtsseite ``/hilfe``.

Aufbau eines Themas::

    "schluessel": {
        "title": "Überschrift im Hilfe-Panel",
        "lead":  "Einleitender Satz (optional).",
        "sections": [
            {"heading": "Abschnitt (optional)", "points": ["Punkt …", "Punkt …"]},
        ],
        "tip": "Kurzer Profi-Tipp am Ende (optional).",
    }

Die Texte in ``items``/``lead``/``tip`` dürfen einfaches Inline-HTML
(``<strong>``, ``<em>``, ``<code>``) enthalten – sie werden im Template mit
``|safe`` ausgegeben. Inhalte stammen ausschließlich aus dieser Datei.
"""

HELP_TOPICS = {
    "uebersicht": {
        "title": "Übersicht – deine Garage",
        "lead": "Die Startseite zeigt alle deine Motorräder als Karten. Von hier aus erreichst du alles Weitere.",
        "sections": [
            {
                "heading": "Was du hier siehst",
                "points": [
                    "Jede <strong>Karte</strong> steht für ein Motorrad mit Titelbild, Kilometerstand und Anzahl der Services.",
                    "Ein <strong>Klick auf eine Karte</strong> öffnet die Detailseite mit Historie, Datenblatt und Dokumenten.",
                ],
            },
            {
                "heading": "Aktionen",
                "points": [
                    "Mit dem <strong>+</strong> in der Fußleiste legst du ein neues Motorrad an.",
                    "Über das <strong>Synchronisieren-Symbol</strong> oben rechts gleichst du lokale Änderungen mit dem Server ab (z.&nbsp;B. nach Offline-Nutzung).",
                ],
            },
        ],
        "tip": "Noch keine Maschine? Tippe auf das <strong>+</strong> und leg dein erstes Motorrad an.",
    },
    "motorrad_neu": {
        "title": "Motorrad anlegen & bearbeiten",
        "lead": "Hier erfasst du die Stammdaten eines Motorrads. Nur Marke und Modell sind nötig – der Rest kann später folgen.",
        "sections": [
            {
                "heading": "Felder",
                "points": [
                    "<strong>Marke & Modell</strong> erscheinen als Titel auf der Karte und überall in der App.",
                    "<strong>Baujahr & Kilometerstand</strong> helfen bei Service-Intervallen und der Übersicht.",
                    "<strong>Titelbild</strong>: Lade ein Foto hoch – es wird auf der Karte und in der Detailansicht gezeigt.",
                ],
            },
        ],
        "tip": "Den Kilometerstand kannst du jederzeit nachpflegen; Service-Einträge nutzen ihn als Bezug.",
    },
    "motorrad_detail": {
        "title": "Motorrad-Detailseite",
        "lead": "Alles zu einem Motorrad an einem Ort – aufgeteilt in drei Tabs.",
        "sections": [
            {
                "heading": "Die Tabs",
                "points": [
                    "<strong>Historie</strong>: alle Service-Einträge und ausgefüllten Checklisten in zeitlicher Reihenfolge.",
                    "<strong>Datenblatt</strong>: technische Typdaten (Reifendruck, Füllmengen, Drehmomente …). Reihenfolge per Ziehen änderbar.",
                    "<strong>Dokumente</strong>: Fahrzeugschein, ABEs, Gutachten und weitere Unterlagen.",
                ],
            },
            {
                "heading": "Aktionen",
                "points": [
                    "Das <strong>Stift-Symbol</strong> oben öffnet die Stammdaten zum Bearbeiten.",
                    "Über die Tabs legst du neue Service-Einträge, Datenblatt-Werte, Checklisten oder Dokumente an.",
                ],
            },
        ],
        "tip": "Gelöscht wird ein Motorrad nur hier in der Einzelansicht – nicht aus der Listenübersicht.",
    },
    "service": {
        "title": "Service-Einträge",
        "lead": "Dokumentiere jede Wartung, Reparatur oder Inspektion mit Datum, Kilometerstand und Kosten.",
        "sections": [
            {
                "heading": "Sinnvoll erfassen",
                "points": [
                    "<strong>Titel</strong> kurz und eindeutig, z.&nbsp;B. „Ölwechsel“ oder „Reifen vorne neu“.",
                    "<strong>Datum & Kilometerstand</strong> machen die Historie nachvollziehbar und sind beim Wiederverkauf Gold wert.",
                    "<strong>Kosten</strong> fließen in die Kostenübersicht des Motorrads ein.",
                    "Im <strong>Notizfeld</strong> kannst du verbaute Teile, Werkstatt oder Besonderheiten festhalten.",
                ],
            },
        ],
        "tip": "Fülle eine Checkliste aus, statt freihändig zu tippen – sie landet automatisch als Eintrag in der Historie.",
    },
    "checklisten": {
        "title": "Checklisten",
        "lead": "Wiederkehrende Arbeiten als Vorlage – einmal anlegen, immer wieder abarbeiten.",
        "sections": [
            {
                "heading": "Vorlagen & Datensätze",
                "points": [
                    "Die Liste zeigt nur deine <strong>Vorlagen</strong> (z.&nbsp;B. „Frühjahrs-Check“).",
                    "Beim <strong>Ausfüllen</strong> entsteht ein abgeschlossener Datensatz, der in der Service-Historie des Motorrads erscheint.",
                    "Eine Vorlage besteht aus <strong>Prüfpunkten</strong>, die du beim Ausfüllen abhakst und kommentierst.",
                ],
            },
            {
                "heading": "Import",
                "points": [
                    "Du kannst Checklisten per <strong>CSV</strong> importieren – die passende Vorlagendatei findest du im Profil.",
                ],
            },
        ],
        "tip": "Lege Vorlagen für typische Intervalle an (z.&nbsp;B. alle 6.000&nbsp;km) und fülle sie bei jeder Wartung neu aus.",
    },
    "technik": {
        "title": "Technische Daten / Datenblatt",
        "lead": "Feste Typdaten deines Motorrads – die Werte, die man immer wieder nachschlägt.",
        "sections": [
            {
                "heading": "Wofür",
                "points": [
                    "Reifendruck, Öl- und Füllmengen, Anzugsdrehmomente, Zündkerzentyp usw.",
                    "Jeder Eintrag ist ein <strong>Bezeichnung–Wert-Paar</strong> und erscheint im Datenblatt-Tab des Motorrads.",
                    "Die <strong>Reihenfolge</strong> lässt sich per Ziehen anpassen, damit Wichtiges oben steht.",
                ],
            },
            {
                "heading": "Import",
                "points": [
                    "Größere Datenblätter kannst du per <strong>CSV</strong> einlesen – Vorlage im Profil verfügbar.",
                ],
            },
        ],
        "tip": "Übertrage die Werte einmalig aus dem Handbuch – danach hast du sie bei jeder Schrauberei griffbereit.",
    },
    "dokumente": {
        "title": "Dokumente",
        "lead": "Bewahre alle Papiere digital beim passenden Motorrad auf.",
        "sections": [
            {
                "heading": "Geeignet",
                "points": [
                    "Fahrzeugschein, ABEs, Gutachten, Rechnungen, Handbücher.",
                    "Lade <strong>PDFs oder Bilder</strong> hoch; jedes Dokument hängt am jeweiligen Motorrad.",
                ],
            },
        ],
        "tip": "Halte ABEs und Gutachten hier bereit – bei einer Kontrolle hast du sie sofort auf dem Handy.",
    },
    "profil": {
        "title": "Profil & Einstellungen",
        "lead": "Persönliche Einstellungen, Vorlagen und der Zugriff auf deine Daten.",
        "sections": [
            {
                "heading": "Darstellung",
                "points": [
                    "<strong>Farbschema</strong>: Hell, Nachtschicht (dunkel) oder System (folgt deinem Gerät).",
                ],
            },
            {
                "heading": "Daten & Sicherheit",
                "points": [
                    "<strong>Backup/Export</strong> als ZIP – je Motorrad eine lesbare PDF und eine maschinenlesbare JSON-Datei (für den Re-Import).",
                    "<strong>Passwort ändern</strong> jederzeit möglich.",
                    "<strong>CSV-Vorlagen & Import</strong> für Checklisten und Datenblätter.",
                    "In der <strong>Gefahrenzone</strong> kannst du dein Profil samt aller Daten unwiderruflich löschen.",
                ],
            },
        ],
        "tip": "Mach vor größeren Änderungen ein Backup – der Export enthält Bilder, Belege und alle Datensätze.",
    },
    "konto": {
        "title": "Konto & Anmeldung",
        "lead": "Dein Zugang zu MotoDB.",
        "sections": [
            {
                "heading": "Gut zu wissen",
                "points": [
                    "Deine Daten gehören zu deinem Konto – nur du siehst deine Motorräder.",
                    "Das <strong>Passwort</strong> kannst du im Profil jederzeit ändern.",
                    "MotoDB läuft im privaten Netz; halte deine Zugangsdaten trotzdem geheim.",
                ],
            },
        ],
        "tip": "Wähle ein eigenes, ausreichend langes Passwort – es schützt deine komplette Fahrzeughistorie.",
    },
    "datenschutz": {
        "title": "Datenschutz",
        "lead": "Welche Daten MotoDB verarbeitet und welche Kontrolle du hast.",
        "sections": [
            {
                "heading": "Kernpunkte",
                "points": [
                    "Es werden nur die Daten gespeichert, die du selbst eingibst oder hochlädst.",
                    "Über den <strong>Export</strong> im Profil bekommst du jederzeit eine vollständige Kopie deiner Daten.",
                    "Beim <strong>Löschen des Profils</strong> werden alle zugehörigen Daten entfernt.",
                ],
            },
        ],
    },
    "admin": {
        "title": "Administration",
        "lead": "Verwaltung von Nutzern, Rollen und Datenbestand (nur für Administratoren).",
        "sections": [
            {
                "heading": "Möglichkeiten",
                "points": [
                    "Nutzerkonten einsehen und Rollen vergeben.",
                    "Den Datenbestand der App im Blick behalten.",
                ],
            },
        ],
        "tip": "Vergib Administratorrechte sparsam – sie erlauben Einblick in die Nutzerverwaltung.",
    },
}
