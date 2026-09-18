"""Anbindung an die Overpass-API (OpenStreetMap), um Unternehmen mit
hinterlegter Website-URL im Stadtgebiet Hamburg zu finden.

Der eigentliche HTTP-Aufruf läuft über eine injizierbare `requests.Session`
(analog zu `crawler.fetcher.Fetcher`), damit Tests ihn ohne echten
Netzwerkzugriff mocken können.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_TIMEOUT_SECONDS = 25.0
DEFAULT_AREA_NAME = "Hamburg"
DEFAULT_USER_AGENT = "WebsiteScoutBot/0.1 (+kontakt: zukunftslabor@infinita-schule.de)"

# Obergrenze für die erste Anfrage, damit die Overpass-API nicht mit einer
# unbegrenzten Ergebnismenge für ein ganzes Stadtgebiet überlastet wird.
DEFAULT_LIMIT = 50

# OSM-Tags, die typischerweise Unternehmen kennzeichnen.
_BUSINESS_TAG_KEYS = ("shop", "office", "craft")
_WEBSITE_TAG_KEYS = ("website", "contact:website")


@dataclass
class OverpassBusiness:
    name: str
    category: str
    address: str
    url: str


@dataclass
class OverpassSearchResult:
    businesses: List[OverpassBusiness]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def build_query(area_name: str = DEFAULT_AREA_NAME, limit: int = DEFAULT_LIMIT) -> str:
    """Baut eine Overpass-QL-Anfrage für Unternehmen mit Website im angegebenen Stadtgebiet."""
    filters = "\n      ".join(
        f'{element}["{tag_key}"]["{website_key}"](area.searchArea);'
        for element in ("node", "way")
        for tag_key in _BUSINESS_TAG_KEYS
        for website_key in _WEBSITE_TAG_KEYS
    )
    return (
        "[out:json][timeout:25];\n"
        f'area["name"="{area_name}"]["boundary"="administrative"]->.searchArea;\n'
        "(\n"
        f"      {filters}\n"
        ");\n"
        f"out center {limit};"
    )


def _extract_category(tags: Dict[str, str]) -> str:
    for key in _BUSINESS_TAG_KEYS:
        if tags.get(key):
            # Für die grobe Anzeige genügt bei allen Office-Typen die
            # einheitliche Kategorie „office“.
            return "office" if key == "office" else tags[key]
    return ""


def _extract_address(tags: Dict[str, str]) -> str:
    street_part = " ".join(
        part for part in [tags.get("addr:street", ""), tags.get("addr:housenumber", "")] if part
    ).strip()
    city_part = " ".join(
        part for part in [tags.get("addr:postcode", ""), tags.get("addr:city", "")] if part
    ).strip()
    return ", ".join(part for part in [street_part, city_part] if part)


def _extract_website(tags: Dict[str, str]) -> str:
    for key in _WEBSITE_TAG_KEYS:
        value = tags.get(key, "").strip()
        if value:
            return value
    return ""


def parse_overpass_response(payload: Dict[str, Any]) -> List[OverpassBusiness]:
    """Wandelt eine Overpass-JSON-Antwort in eine Liste von Unternehmen um.

    Es werden nur Einträge mit einer Website-URL übernommen, doppelte
    URLs werden entfernt (die erste Fundstelle gewinnt).
    """
    businesses: List[OverpassBusiness] = []
    seen_urls = set()

    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        url = _extract_website(tags)
        if not url:
            continue

        dedupe_key = url.rstrip("/").lower()
        if dedupe_key in seen_urls:
            continue
        seen_urls.add(dedupe_key)

        businesses.append(
            OverpassBusiness(
                name=tags.get("name", "").strip(),
                category=_extract_category(tags),
                address=_extract_address(tags),
                url=url,
            )
        )

    return businesses


class OverpassSource:
    """Sucht Unternehmen mit Website-URL im Stadtgebiet Hamburg über die Overpass-API."""

    def __init__(
        self,
        area_name: str = DEFAULT_AREA_NAME,
        limit: int = DEFAULT_LIMIT,
        api_url: str = DEFAULT_OVERPASS_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        session: Optional[requests.Session] = None,
    ):
        self.area_name = area_name
        self.limit = limit
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.session = session or requests.Session()

    def search(self) -> OverpassSearchResult:
        """Fragt die Overpass-API ab und liefert gefundene Unternehmen mit Website.

        HTTP- und API-Fehler (Timeout, Verbindungsfehler, Fehlerstatuscode,
        ungültiges JSON) werden abgefangen und als verständliche
        Fehlermeldung in `OverpassSearchResult.error` zurückgegeben, statt
        eine Ausnahme zu werfen.
        """
        query = build_query(self.area_name, self.limit)

        try:
            response = self.session.post(
                self.api_url,
                data={"data": query},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
            )
        except requests.Timeout:
            return OverpassSearchResult(
                businesses=[],
                error=(
                    f"Zeitüberschreitung bei der Anfrage an die Overpass-API "
                    f"(Timeout nach {self.timeout_seconds}s)."
                ),
            )
        except requests.RequestException as exc:
            return OverpassSearchResult(
                businesses=[],
                error=f"Fehler bei der Anfrage an die Overpass-API: {exc}",
            )

        if response.status_code != 200:
            return OverpassSearchResult(
                businesses=[],
                error=f"Overpass-API antwortete mit Statuscode {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return OverpassSearchResult(
                businesses=[],
                error=f"Antwort der Overpass-API konnte nicht als JSON gelesen werden: {exc}",
            )

        return OverpassSearchResult(businesses=parse_overpass_response(payload))
