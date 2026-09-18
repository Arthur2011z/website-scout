"""SQLite-Anbindung für den Website Scout."""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS websites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    name TEXT,
    city TEXT,
    title TEXT,
    meta_description TEXT,
    text_length INTEGER DEFAULT 0,
    has_impressum INTEGER DEFAULT 0,
    score REAL DEFAULT 0,
    status_code INTEGER,
    crawled_at TEXT,
    final_url TEXT DEFAULT '',
    response_time_seconds REAL,
    has_viewport INTEGER DEFAULT 0,
    has_kontakt_link INTEGER DEFAULT 0,
    contact_email_count INTEGER DEFAULT 0,
    contact_phone_count INTEGER DEFAULT 0,
    explanations TEXT DEFAULT '[]'
);
"""

# Spalten, die nachträglich zu bereits bestehenden Datenbanken hinzugefügt
# werden müssen, damit ältere Datenbestände (erzeugt vor Einführung dieser
# Felder) weiterhin gelesen werden können. Jede Spalte erhält einen sicheren
# Default, sodass bestehende Zeilen gültige Werte bekommen.
MIGRATION_COLUMNS = {
    "final_url": "TEXT DEFAULT ''",
    "response_time_seconds": "REAL",
    "has_viewport": "INTEGER DEFAULT 0",
    "has_kontakt_link": "INTEGER DEFAULT 0",
    "contact_email_count": "INTEGER DEFAULT 0",
    "contact_phone_count": "INTEGER DEFAULT 0",
    "explanations": "TEXT DEFAULT '[]'",
}


@dataclass
class WebsiteRecord:
    url: str
    name: str = ""
    city: str = ""
    title: str = ""
    meta_description: str = ""
    text_length: int = 0
    has_impressum: bool = False
    score: float = 0.0
    status_code: Optional[int] = None
    crawled_at: str = ""
    # Tatsächlich abgerufene Adresse (z. B. nach HTTP->HTTPS-Weiterleitung).
    final_url: str = ""
    # Gemessene Antwortzeit des Abrufs in Sekunden.
    response_time_seconds: Optional[float] = None
    has_viewport: bool = False
    has_kontakt_link: bool = False
    contact_email_count: int = 0
    contact_phone_count: int = 0
    # Kurze, nachvollziehbare deutsche Begründungen pro Bewertungskriterium.
    explanations: List[str] = field(default_factory=list)
    # Stabile numerische ID aus der Datenbank (AUTOINCREMENT). Wird beim Anlegen
    # noch nicht vergeben, sondern erst beim Lesen aus der Datenbank gesetzt;
    # dient u. a. dem Report-Generator als sichere, stabile Grundlage für
    # Detailseiten-Dateinamen.
    id: Optional[int] = None


class Database:
    """Dünner Wrapper um sqlite3 für die Ablage von Crawling-Ergebnissen."""

    def __init__(self, db_path: str = ":memory:"):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(SCHEMA)
        self._migrate_schema()
        self.connection.commit()

    def _migrate_schema(self) -> None:
        """Ergänzt fehlende Spalten bei einer bereits bestehenden, älteren
        Datenbank, ohne vorhandene Daten zu verändern oder zu verwerfen."""
        existing_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(websites)")
        }
        for column, ddl in MIGRATION_COLUMNS.items():
            if column not in existing_columns:
                self.connection.execute(f"ALTER TABLE websites ADD COLUMN {column} {ddl}")

    def upsert_website(self, record: WebsiteRecord) -> None:
        """Legt eine Website neu an oder aktualisiert sie anhand ihrer URL."""
        self.connection.execute(
            """
            INSERT INTO websites (
                url, name, city, title, meta_description,
                text_length, has_impressum, score, status_code, crawled_at,
                final_url, response_time_seconds, has_viewport, has_kontakt_link,
                contact_email_count, contact_phone_count, explanations
            )
            VALUES (
                :url, :name, :city, :title, :meta_description,
                :text_length, :has_impressum, :score, :status_code, :crawled_at,
                :final_url, :response_time_seconds, :has_viewport, :has_kontakt_link,
                :contact_email_count, :contact_phone_count, :explanations
            )
            ON CONFLICT(url) DO UPDATE SET
                name=excluded.name,
                city=excluded.city,
                title=excluded.title,
                meta_description=excluded.meta_description,
                text_length=excluded.text_length,
                has_impressum=excluded.has_impressum,
                score=excluded.score,
                status_code=excluded.status_code,
                crawled_at=excluded.crawled_at,
                final_url=excluded.final_url,
                response_time_seconds=excluded.response_time_seconds,
                has_viewport=excluded.has_viewport,
                has_kontakt_link=excluded.has_kontakt_link,
                contact_email_count=excluded.contact_email_count,
                contact_phone_count=excluded.contact_phone_count,
                explanations=excluded.explanations
            """,
            {
                "url": record.url,
                "name": record.name,
                "city": record.city,
                "title": record.title,
                "meta_description": record.meta_description,
                "text_length": record.text_length,
                "has_impressum": int(record.has_impressum),
                "score": record.score,
                "status_code": record.status_code,
                "crawled_at": record.crawled_at,
                "final_url": record.final_url,
                "response_time_seconds": record.response_time_seconds,
                "has_viewport": int(record.has_viewport),
                "has_kontakt_link": int(record.has_kontakt_link),
                "contact_email_count": record.contact_email_count,
                "contact_phone_count": record.contact_phone_count,
                "explanations": json.dumps(record.explanations, ensure_ascii=False),
            },
        )
        self.connection.commit()

    def get_all_websites(self) -> List[WebsiteRecord]:
        cursor = self.connection.execute("SELECT * FROM websites ORDER BY score DESC")
        rows = cursor.fetchall()
        return [
            WebsiteRecord(
                id=row["id"],
                url=row["url"],
                name=row["name"],
                city=row["city"],
                title=row["title"],
                meta_description=row["meta_description"],
                text_length=row["text_length"],
                has_impressum=bool(row["has_impressum"]),
                score=row["score"],
                status_code=row["status_code"],
                crawled_at=row["crawled_at"],
                final_url=row["final_url"] or "",
                response_time_seconds=row["response_time_seconds"],
                has_viewport=bool(row["has_viewport"]),
                has_kontakt_link=bool(row["has_kontakt_link"]),
                contact_email_count=row["contact_email_count"] or 0,
                contact_phone_count=row["contact_phone_count"] or 0,
                explanations=_load_explanations(row["explanations"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()


def _load_explanations(raw: Optional[str]) -> List[str]:
    """Liest die gespeicherten Begründungen robust aus, auch wenn das Feld bei
    älteren Datensätzen (vor der Migration) leer oder NULL ist."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []
