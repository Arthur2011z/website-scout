"""Einstiegspunkt für den Website Scout (Grundgerüst).

Lädt Konfiguration und Start-Quellen, ruft sie ab, wertet sie mit
einfachen Regeln aus und schreibt die Ergebnisse in SQLite sowie einen
HTML-Report. Es findet noch keine automatische Website-Suche und keine
komplexe Inhaltsanalyse statt - das ist für spätere Ausbaustufen vorgesehen.

Optional (per Schalter `overpass.enabled` in config.yaml) werden zusätzlich
Unternehmen mit Website-URL über die Overpass-API (OpenStreetMap) gesucht
und als weitere Kandidaten in denselben Ablauf übernommen.
"""
import datetime
from pathlib import Path
from typing import List

import yaml

from analysis.extractor import extract_page_info
from crawler.fetcher import Fetcher
from crawler.robots import RobotsChecker
from database.db import Database, WebsiteRecord
from report.generator import render_report
from scoring.scorer import score_page
from sources.loader import Source, load_sources
from sources.overpass_source import OverpassSource

BASE_DIR = Path(__file__).resolve().parent


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_overpass_sources(config: dict) -> List[Source]:
    """Sucht (falls in config.yaml aktiviert) Unternehmen mit Website-URL über
    die Overpass-API und wandelt sie in Kandidaten für den bestehenden Ablauf um.

    Schlägt die Overpass-Suche fehl (z. B. Timeout, Verbindungsfehler,
    Fehlerstatuscode), wird eine verständliche Meldung ausgegeben und eine
    leere Liste zurückgegeben, statt das Programm abstürzen zu lassen.
    """
    overpass_config = config.get("overpass") or {}
    if not overpass_config.get("enabled", False):
        return []

    overpass = OverpassSource(
        area_name=overpass_config.get("area_name", "Hamburg"),
        limit=overpass_config.get("limit", 50),
        user_agent=config["crawler"]["user_agent"],
    )
    result = overpass.search()

    if not result.ok:
        print(f"Hinweis: Overpass-Suche übersprungen ({result.error})")
        return []

    return [
        Source(name=business.name or business.url, url=business.url, city=overpass.area_name)
        for business in result.businesses
    ]


def run(config_path: str = "config.yaml", sources_path: str = "sources/seed_urls.yaml") -> None:
    config = load_config(config_path)

    robots_checker = RobotsChecker(
        user_agent=config["crawler"]["user_agent"],
        timeout_seconds=config["crawler"]["timeout_seconds"],
    )
    fetcher = Fetcher(
        user_agent=config["crawler"]["user_agent"],
        rate_limit_seconds=config["crawler"]["rate_limit_seconds"],
        timeout_seconds=config["crawler"]["timeout_seconds"],
        robots_checker=robots_checker,
    )
    db = Database(config["database"]["path"])
    weights = config["scoring"]["weights"]

    sources = load_sources(sources_path) + load_overpass_sources(config)

    for source in sources:
        result = fetcher.fetch(source.url)
        crawled_at = datetime.datetime.now().isoformat(timespec="seconds")

        if not result.ok:
            failure_reason = result.error or f"HTTP-Status {result.status_code}"
            db.upsert_website(
                WebsiteRecord(
                    url=source.url,
                    name=source.name,
                    city=source.city,
                    status_code=result.status_code,
                    crawled_at=crawled_at,
                    final_url=result.final_url,
                    response_time_seconds=result.response_time_seconds,
                    explanations=[f"Abruf fehlgeschlagen: {failure_reason} (0 Punkte)"],
                )
            )
            continue

        page_info = extract_page_info(result.html, source.url)
        score_result = score_page(
            page_info,
            weights,
            status_code=result.status_code,
            final_url=result.final_url,
            response_time_seconds=result.response_time_seconds,
        )

        db.upsert_website(
            WebsiteRecord(
                url=source.url,
                name=source.name,
                city=source.city,
                title=page_info.title,
                meta_description=page_info.meta_description,
                text_length=page_info.text_length,
                has_impressum=page_info.has_impressum,
                score=score_result.score,
                status_code=result.status_code,
                crawled_at=crawled_at,
                final_url=result.final_url,
                response_time_seconds=result.response_time_seconds,
                has_viewport=page_info.has_viewport,
                has_kontakt_link=page_info.has_kontakt_link,
                contact_email_count=len(page_info.emails),
                contact_phone_count=len(page_info.phones),
                explanations=score_result.explanations,
            )
        )

    render_report(db, config)
    db.close()


if __name__ == "__main__":
    run()
