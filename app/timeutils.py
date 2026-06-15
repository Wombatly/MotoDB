from datetime import datetime, timezone


def utcnow() -> datetime:
    """Aktuelle UTC-Zeit als *naives* datetime.

    Ersetzt das deprecatete ``datetime.utcnow()``. Bewusst naiv (tzinfo
    entfernt), damit die Werte konsistent zu den bereits in der DB
    gespeicherten naiven UTC-Zeitstempeln bleiben und Vergleiche nicht
    an "offset-naive vs offset-aware" scheitern.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
