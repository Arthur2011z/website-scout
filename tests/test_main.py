from unittest.mock import MagicMock

import main
from crawler.fetcher import FetchResult
from database.db import Database
from sources.loader import Source
from sources.overpass_source import OverpassBusiness, OverpassSearchResult

MINIMAL_CONFIG = {
    "crawler": {
        "user_agent": "TestBot/1.0",
        "rate_limit_seconds": 0,
        "timeout_seconds": 5,
        "max_pages_per_domain": 5,
    },
}


def _config_yaml(tmp_path, overpass_block: str = "") -> str:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
region:
  city: "Hamburg"
  country: "Deutschland"
crawler:
  user_agent: "TestBot/1.0"
  rate_limit_seconds: 0
  timeout_seconds: 5
  max_pages_per_domain: 5
scoring:
  weights:
    has_title: 1.0
    has_meta_description: 1.0
    has_impressum: 2.0
    has_text: 1.0
  min_score_relevant: 3.0
database:
  path: "{(tmp_path / 'test.db').as_posix()}"
output:
  directory: "{(tmp_path / 'output').as_posix()}"
{overpass_block}
""",
        encoding="utf-8",
    )
    return str(config_file)


def _seed_yaml(tmp_path) -> str:
    seed_file = tmp_path / "seed.yaml"
    seed_file.write_text(
        "sources:\n"
        '  - name: "Seed Betrieb"\n'
        '    url: "https://seed.example"\n'
        '    city: "Hamburg"\n',
        encoding="utf-8",
    )
    return str(seed_file)


def _fake_overpass_html():
    return "<html><head><title>T</title></head><body>Impressum Text</body></html>"


# --- load_overpass_sources -------------------------------------------------


def test_load_overpass_sources_disabled_by_default():
    assert main.load_overpass_sources(MINIMAL_CONFIG) == []


def test_load_overpass_sources_disabled_when_flag_false():
    config = {**MINIMAL_CONFIG, "overpass": {"enabled": False}}
    assert main.load_overpass_sources(config) == []


def test_load_overpass_sources_returns_candidates_with_website(monkeypatch):
    fake_result = OverpassSearchResult(
        businesses=[
            OverpassBusiness(
                name="Bäckerei Beispiel", category="bakery", address="", url="https://baeckerei.example"
            ),
            OverpassBusiness(name="", category="office", address="", url="https://noname.example"),
        ]
    )
    fake_instance = MagicMock()
    fake_instance.search.return_value = fake_result
    fake_instance.area_name = "Hamburg"
    fake_class = MagicMock(return_value=fake_instance)
    monkeypatch.setattr(main, "OverpassSource", fake_class)

    config = {**MINIMAL_CONFIG, "overpass": {"enabled": True, "area_name": "Hamburg", "limit": 50}}
    sources = main.load_overpass_sources(config)

    assert sources == [
        Source(name="Bäckerei Beispiel", url="https://baeckerei.example", city="Hamburg"),
        Source(name="https://noname.example", url="https://noname.example", city="Hamburg"),
    ]
    fake_class.assert_called_once_with(area_name="Hamburg", limit=50, user_agent="TestBot/1.0")


def test_load_overpass_sources_handles_error_without_crashing(monkeypatch, capsys):
    fake_result = OverpassSearchResult(businesses=[], error="Zeitüberschreitung bei der Anfrage.")
    fake_instance = MagicMock()
    fake_instance.search.return_value = fake_result
    monkeypatch.setattr(main, "OverpassSource", MagicMock(return_value=fake_instance))

    config = {**MINIMAL_CONFIG, "overpass": {"enabled": True}}
    sources = main.load_overpass_sources(config)

    assert sources == []
    assert "Zeitüberschreitung" in capsys.readouterr().out


# --- run() integration -------------------------------------------------


def test_run_keeps_seed_only_behaviour_when_overpass_disabled(tmp_path, monkeypatch):
    config_path = _config_yaml(tmp_path, overpass_block="overpass:\n  enabled: false\n")
    sources_path = _seed_yaml(tmp_path)

    monkeypatch.setattr(
        main.Fetcher,
        "fetch",
        lambda self, url: FetchResult(url=url, status_code=200, html=_fake_overpass_html()),
    )
    overpass_class = MagicMock()
    monkeypatch.setattr(main, "OverpassSource", overpass_class)

    main.run(config_path=config_path, sources_path=sources_path)

    overpass_class.assert_not_called()
    db = Database(str(tmp_path / "test.db"))
    try:
        urls = {w.url for w in db.get_all_websites()}
    finally:
        db.close()
    assert urls == {"https://seed.example"}


def test_run_merges_seed_and_overpass_candidates(tmp_path, monkeypatch):
    config_path = _config_yaml(
        tmp_path, overpass_block='overpass:\n  enabled: true\n  area_name: "Hamburg"\n  limit: 50\n'
    )
    sources_path = _seed_yaml(tmp_path)

    fake_result = OverpassSearchResult(
        businesses=[
            OverpassBusiness(name="OSM Betrieb", category="shop", address="", url="https://osm.example")
        ]
    )
    fake_instance = MagicMock()
    fake_instance.search.return_value = fake_result
    fake_instance.area_name = "Hamburg"
    monkeypatch.setattr(main, "OverpassSource", MagicMock(return_value=fake_instance))

    monkeypatch.setattr(
        main.Fetcher,
        "fetch",
        lambda self, url: FetchResult(url=url, status_code=200, html=_fake_overpass_html()),
    )

    main.run(config_path=config_path, sources_path=sources_path)

    db = Database(str(tmp_path / "test.db"))
    try:
        urls = {w.url for w in db.get_all_websites()}
    finally:
        db.close()
    assert urls == {"https://seed.example", "https://osm.example"}


def test_run_passes_robots_checker_to_fetcher(tmp_path, monkeypatch):
    config_path = _config_yaml(tmp_path, overpass_block="overpass:\n  enabled: false\n")
    sources_path = _seed_yaml(tmp_path)

    captured = {}
    real_fetcher_class = main.Fetcher

    class FetcherSpy(real_fetcher_class):
        def __init__(self, *args, **kwargs):
            captured["robots_checker"] = kwargs.get("robots_checker")
            super().__init__(*args, **kwargs)

        def fetch(self, url):
            return FetchResult(url=url, status_code=200, html=_fake_overpass_html())

    monkeypatch.setattr(main, "Fetcher", FetcherSpy)

    main.run(config_path=config_path, sources_path=sources_path)

    assert isinstance(captured["robots_checker"], main.RobotsChecker)


def test_run_stores_extended_fetch_and_scoring_data(tmp_path, monkeypatch):
    config_path = _config_yaml(tmp_path, overpass_block="overpass:\n  enabled: false\n")
    sources_path = _seed_yaml(tmp_path)

    rich_html = (
        "<html><head><title>Handwerk Beispiel</title>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "</head><body><a href=\"/impressum\">Impressum</a>"
        '<a href="/kontakt">Kontakt</a><a href="mailto:info@beispiel.example">Mail</a>'
        "</body></html>"
    )
    monkeypatch.setattr(
        main.Fetcher,
        "fetch",
        lambda self, url: FetchResult(
            url=url,
            status_code=200,
            html=rich_html,
            final_url=url.replace("https://", "https://www."),
            response_time_seconds=0.75,
        ),
    )

    main.run(config_path=config_path, sources_path=sources_path)

    db = Database(str(tmp_path / "test.db"))
    try:
        website = db.get_all_websites()[0]
    finally:
        db.close()

    assert website.final_url == "https://www.seed.example"
    assert website.response_time_seconds == 0.75
    assert website.has_viewport is True
    assert website.has_kontakt_link is True
    assert website.contact_email_count == 1
    assert website.has_impressum is True
    assert website.explanations  # nachvollziehbare Begründungen wurden gespeichert
    assert any("HTTPS" in e for e in website.explanations)


def test_run_stores_failure_explanation_when_fetch_fails(tmp_path, monkeypatch):
    config_path = _config_yaml(tmp_path, overpass_block="overpass:\n  enabled: false\n")
    sources_path = _seed_yaml(tmp_path)

    monkeypatch.setattr(
        main.Fetcher,
        "fetch",
        lambda self, url: FetchResult(url=url, status_code=500, html=None, error=None),
    )

    main.run(config_path=config_path, sources_path=sources_path)

    db = Database(str(tmp_path / "test.db"))
    try:
        website = db.get_all_websites()[0]
    finally:
        db.close()

    assert website.score == 0.0
    assert website.explanations
    assert "fehlgeschlagen" in website.explanations[0]


def test_run_does_not_crash_when_overpass_fails(tmp_path, monkeypatch, capsys):
    config_path = _config_yaml(tmp_path, overpass_block="overpass:\n  enabled: true\n")
    sources_path = _seed_yaml(tmp_path)

    fake_instance = MagicMock()
    fake_instance.search.return_value = OverpassSearchResult(businesses=[], error="Statuscode 504.")
    monkeypatch.setattr(main, "OverpassSource", MagicMock(return_value=fake_instance))

    monkeypatch.setattr(
        main.Fetcher,
        "fetch",
        lambda self, url: FetchResult(url=url, status_code=200, html=_fake_overpass_html()),
    )

    main.run(config_path=config_path, sources_path=sources_path)

    assert "Statuscode 504" in capsys.readouterr().out
    db = Database(str(tmp_path / "test.db"))
    try:
        urls = {w.url for w in db.get_all_websites()}
    finally:
        db.close()
    assert urls == {"https://seed.example"}
