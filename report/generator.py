"""Report-Generator: erzeugt aus den gespeicherten Website-Datensätzen eine
statische HTML-Übersicht (index.html) sowie eine eigene Detailseite je
Website. Nutzt ausschließlich das bereits vorhandene Jinja2-Setup und
schreibt reine, lokale HTML-Dateien - kein Webserver, keine neue
Abhängigkeit.
"""
import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from database.db import Database, WebsiteRecord

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

INDEX_TEMPLATE = "index.html.j2"
DETAIL_TEMPLATE = "detail.html.j2"


def detail_filename(website_id: int) -> str:
    """Erzeugt einen stabilen, sicheren Dateinamen für die Detailseite.

    Basiert bewusst ausschließlich auf der numerischen, von der Datenbank
    vergebenen ID (statt z. B. auf Name oder URL), damit der Dateiname weder
    von extern gescrapten Daten abhängt noch sich zwischen zwei Report-Läufen
    ändert, nur weil sich die Sortierung nach Score verschoben hat.
    """
    return f"website-{website_id:04d}.html"


def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def _is_https(website: WebsiteRecord) -> bool:
    effective_url = (website.final_url or website.url or "").lower()
    return effective_url.startswith("https://")


def render_report(db: Database, config: dict) -> None:
    """Rendert index.html (Übersicht) sowie eine Detailseite je Website in
    das konfigurierte Output-Verzeichnis."""
    env = _build_environment()
    index_template = env.get_template(INDEX_TEMPLATE)
    detail_template = env.get_template(DETAIL_TEMPLATE)

    websites: List[WebsiteRecord] = db.get_all_websites()
    generated_at = datetime.datetime.now().isoformat(timespec="seconds")

    entries = [
        {"website": website, "detail_filename": detail_filename(website.id)}
        for website in websites
        if website.id is not None
    ]

    output_dir = Path(config["output"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    index_html = index_template.render(
        city=config["region"]["city"],
        generated_at=generated_at,
        entries=entries,
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    for entry in entries:
        website = entry["website"]
        detail_html = detail_template.render(
            city=config["region"]["city"],
            generated_at=generated_at,
            website=website,
            is_https=_is_https(website),
        )
        (output_dir / entry["detail_filename"]).write_text(detail_html, encoding="utf-8")
