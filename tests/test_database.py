import sqlite3

from database.db import Database, WebsiteRecord

LEGACY_SCHEMA = """
CREATE TABLE websites (
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
    crawled_at TEXT
);
"""


def test_upsert_and_get_all_websites():
    db = Database(":memory:")
    try:
        db.upsert_website(WebsiteRecord(url="https://a.example", name="A", score=1.5))
        db.upsert_website(WebsiteRecord(url="https://b.example", name="B", score=3.0))

        websites = db.get_all_websites()

        assert len(websites) == 2
        assert websites[0].url == "https://b.example"  # höchster Score zuerst
    finally:
        db.close()


def test_upsert_updates_existing_entry():
    db = Database(":memory:")
    try:
        db.upsert_website(WebsiteRecord(url="https://a.example", score=1.0))
        db.upsert_website(WebsiteRecord(url="https://a.example", score=9.0))

        websites = db.get_all_websites()

        assert len(websites) == 1
        assert websites[0].score == 9.0
    finally:
        db.close()


def test_upsert_and_read_extended_fields_roundtrip():
    db = Database(":memory:")
    try:
        db.upsert_website(
            WebsiteRecord(
                url="https://a.example",
                final_url="https://a.example/",
                response_time_seconds=0.42,
                has_viewport=True,
                has_kontakt_link=True,
                contact_email_count=2,
                contact_phone_count=1,
                explanations=["Seitentitel vorhanden: „Titel“ (+1 Punkte)", "Kein Impressum-Hinweis gefunden (0 Punkte)"],
            )
        )

        website = db.get_all_websites()[0]

        assert website.final_url == "https://a.example/"
        assert website.response_time_seconds == 0.42
        assert website.has_viewport is True
        assert website.has_kontakt_link is True
        assert website.contact_email_count == 2
        assert website.contact_phone_count == 1
        assert website.explanations == [
            "Seitentitel vorhanden: „Titel“ (+1 Punkte)",
            "Kein Impressum-Hinweis gefunden (0 Punkte)",
        ]
    finally:
        db.close()


def test_database_migrates_legacy_schema_and_keeps_existing_data(tmp_path):
    db_path = tmp_path / "legacy.db"

    # Simuliert eine Datenbank, die vor Einführung der neuen Spalten angelegt wurde.
    legacy_connection = sqlite3.connect(str(db_path))
    legacy_connection.executescript(LEGACY_SCHEMA)
    legacy_connection.execute(
        "INSERT INTO websites (url, name, city, title, score, status_code, crawled_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("https://alt.example", "Alt GmbH", "Hamburg", "Alte Seite", 4.0, 200, "2024-01-01T00:00:00"),
    )
    legacy_connection.commit()
    legacy_connection.close()

    db = Database(str(db_path))
    try:
        websites = db.get_all_websites()

        assert len(websites) == 1
        website = websites[0]
        assert website.url == "https://alt.example"
        assert website.name == "Alt GmbH"
        assert website.score == 4.0
        # Neue Felder fehlten im alten Datensatz und müssen auf sichere Defaults fallen.
        assert website.final_url == ""
        assert website.response_time_seconds is None
        assert website.has_viewport is False
        assert website.has_kontakt_link is False
        assert website.contact_email_count == 0
        assert website.contact_phone_count == 0
        assert website.explanations == []

        # Die migrierte Datenbank muss weiterhin normal beschreibbar sein.
        db.upsert_website(WebsiteRecord(url="https://neu.example", score=1.0, explanations=["Test"]))
        assert {w.url for w in db.get_all_websites()} == {"https://alt.example", "https://neu.example"}
    finally:
        db.close()
