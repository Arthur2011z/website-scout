"""Regelbasierte Bewertung einer Website mit konfigurierbaren Gewichten und
nachvollziehbaren deutschen Begründungen pro Kriterium."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from analysis.extractor import PageInfo

DEFAULT_WEIGHTS: Dict[str, float] = {
    "has_title": 1.0,
    "has_meta_description": 1.0,
    "has_impressum": 2.0,
    "has_text": 1.0,
    "has_https": 1.0,
    "status_ok": 1.0,
    "has_viewport": 1.0,
    "has_kontakt": 1.0,
    "response_time_ok": 1.0,
}

# Antwortzeiten bis zu diesem Wert (in Sekunden) gelten als ausreichend schnell.
DEFAULT_MAX_RESPONSE_TIME_SECONDS = 3.0


@dataclass
class ScoreResult:
    """Ergebnis einer Bewertung: Gesamt-Score plus eine kurze deutsche
    Begründung je geprüftem Kriterium, in der Reihenfolge der Prüfung."""

    score: float
    explanations: List[str] = field(default_factory=list)


def score_page(
    page_info: PageInfo,
    weights: Optional[Dict[str, float]] = None,
    *,
    status_code: Optional[int] = None,
    final_url: str = "",
    response_time_seconds: Optional[float] = None,
    max_response_time_seconds: float = DEFAULT_MAX_RESPONSE_TIME_SECONDS,
) -> ScoreResult:
    """Berechnet einen Score aus wenigen, leicht erklärbaren Signalen und
    liefert für jedes geprüfte Kriterium eine nachvollziehbare Begründung.

    `status_code`, `final_url` und `response_time_seconds` stammen aus dem
    `FetchResult` des Crawlers und sind optional, damit die Funktion weiterhin
    ausschließlich mit einem `PageInfo` aufgerufen werden kann.
    """
    weights = weights or DEFAULT_WEIGHTS
    score = 0.0
    explanations: List[str] = []

    def award(condition: bool, key: str, positive: str, negative: str) -> None:
        nonlocal score
        weight = weights.get(key, 0.0)
        if condition:
            score += weight
            explanations.append(f"{positive} (+{weight:g} Punkte)")
        else:
            explanations.append(f"{negative} (0 Punkte)")

    award(
        bool(page_info.title),
        "has_title",
        f"Seitentitel vorhanden: „{page_info.title}“",
        "Kein Seitentitel gefunden",
    )
    award(
        bool(page_info.meta_description),
        "has_meta_description",
        "Meta-Beschreibung vorhanden",
        "Keine Meta-Beschreibung gefunden",
    )
    award(
        page_info.has_impressum,
        "has_impressum",
        "Hinweis auf ein Impressum gefunden",
        "Kein Hinweis auf ein Impressum gefunden",
    )
    award(
        page_info.text_length > 0,
        "has_text",
        f"Sichtbarer Text vorhanden ({page_info.text_length} Zeichen)",
        "Kein sichtbarer Text gefunden",
    )
    award(
        page_info.has_viewport,
        "has_viewport",
        "Viewport-Meta-Tag vorhanden (spricht für Mobilfreundlichkeit)",
        "Kein Viewport-Meta-Tag gefunden (evtl. nicht mobilfreundlich)",
    )

    has_contact = page_info.has_kontakt_link or bool(page_info.emails) or bool(page_info.phones)
    award(
        has_contact,
        "has_kontakt",
        f"Kontaktmöglichkeit gefunden ({len(page_info.emails)} E-Mail(s), "
        f"{len(page_info.phones)} Telefonnummer(n), Kontakt-Link: "
        f"{'ja' if page_info.has_kontakt_link else 'nein'})",
        "Keine Kontaktmöglichkeit gefunden (weder Link noch E-Mail/Telefon)",
    )

    effective_url = (final_url or page_info.url or "").lower()
    award(
        effective_url.startswith("https://"),
        "has_https",
        "Website ist über HTTPS erreichbar",
        "Website ist nicht über HTTPS erreichbar",
    )

    if status_code is not None:
        award(
            status_code == 200,
            "status_ok",
            f"HTTP-Status {status_code} (erfolgreich abgerufen)",
            f"HTTP-Status {status_code} (kein erfolgreicher Abruf)",
        )
    else:
        explanations.append("HTTP-Status unbekannt, da kein Statuscode übergeben wurde (0 Punkte)")

    if response_time_seconds is not None:
        award(
            response_time_seconds <= max_response_time_seconds,
            "response_time_ok",
            f"Antwortzeit von {response_time_seconds:.2f}s liegt innerhalb des "
            f"Zielwerts von {max_response_time_seconds:g}s",
            f"Antwortzeit von {response_time_seconds:.2f}s liegt über dem "
            f"Zielwert von {max_response_time_seconds:g}s",
        )
    else:
        explanations.append("Antwortzeit unbekannt, da keine Messung übergeben wurde (0 Punkte)")

    return ScoreResult(score=score, explanations=explanations)
