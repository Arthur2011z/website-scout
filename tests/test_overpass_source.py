import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from sources.overpass_source import (
    DEFAULT_AREA_NAME,
    OverpassSource,
    build_query,
    parse_overpass_response,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def make_response(status_code=200, json_data=None, raise_json_error=False):
    response = MagicMock(status_code=status_code)
    if raise_json_error:
        response.json.side_effect = ValueError("kaputtes JSON")
    else:
        response.json.return_value = json_data
    return response


def test_build_query_contains_area_and_limit():
    query = build_query(area_name="Hamburg", limit=50)

    assert 'area["name"="Hamburg"]' in query
    assert "out center 50;" in query
    assert '["website"]' in query
    assert '["contact:website"]' in query


def test_parse_overpass_response_keeps_only_entries_with_website():
    payload = load_fixture("overpass_sample_response.json")

    businesses = parse_overpass_response(payload)

    urls = [b.url for b in businesses]
    assert "https://baeckerei-beispiel.example" in urls
    # Element 333 ("Ohne Website GmbH") hat keine Website und darf nicht auftauchen.
    assert all(b.name != "Ohne Website GmbH" for b in businesses)


def test_parse_overpass_response_removes_duplicate_urls():
    payload = load_fixture("overpass_sample_response.json")

    businesses = parse_overpass_response(payload)

    # Element 111 und 444 verweisen (bis auf einen Slash) auf dieselbe URL.
    matching = [b for b in businesses if b.url.rstrip("/").lower() == "https://baeckerei-beispiel.example"]
    assert len(matching) == 1
    assert matching[0].name == "Bäckerei Beispiel"


def test_parse_overpass_response_extracts_fields():
    payload = load_fixture("overpass_sample_response.json")

    businesses = parse_overpass_response(payload)
    bakery = next(b for b in businesses if b.url.startswith("https://baeckerei-beispiel.example"))

    assert bakery.category == "bakery"
    assert bakery.address == "Musterstraße 1, 20095 Hamburg"

    it_consulting = next(b for b in businesses if "it-beratung" in b.url)
    assert it_consulting.name == "IT-Beratung Beispiel"
    assert it_consulting.category == "office"
    assert it_consulting.url == "https://it-beratung-beispiel.example/"


def test_search_returns_deduplicated_businesses_with_website():
    payload = load_fixture("overpass_sample_response.json")
    session = MagicMock()
    session.post.return_value = make_response(json_data=payload)

    source = OverpassSource(session=session)
    result = source.search()

    assert result.ok
    # 5 Rohtreffer, einer ohne Website, einer davon ein Duplikat -> 3 Ergebnisse.
    assert len(result.businesses) == 3
    assert len({b.url.rstrip("/").lower() for b in result.businesses}) == 3


def test_search_sends_expected_request():
    session = MagicMock()
    session.post.return_value = make_response(json_data={"elements": []})

    source = OverpassSource(session=session, area_name=DEFAULT_AREA_NAME, limit=50)
    source.search()

    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args[0] == "https://overpass-api.de/api/interpreter"
    assert "data" in kwargs["data"]
    assert kwargs["headers"]["User-Agent"]
    assert kwargs["timeout"] == 25.0


def test_search_handles_timeout():
    session = MagicMock()
    session.post.side_effect = requests.Timeout("timed out")

    source = OverpassSource(session=session)
    result = source.search()

    assert not result.ok
    assert result.businesses == []
    assert "Zeitüberschreitung" in result.error


def test_search_handles_connection_error():
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("boom")

    source = OverpassSource(session=session)
    result = source.search()

    assert not result.ok
    assert result.businesses == []
    assert "boom" in result.error


def test_search_handles_http_error_status():
    session = MagicMock()
    session.post.return_value = make_response(status_code=504)

    source = OverpassSource(session=session)
    result = source.search()

    assert not result.ok
    assert "504" in result.error


def test_search_handles_invalid_json():
    session = MagicMock()
    session.post.return_value = make_response(raise_json_error=True)

    source = OverpassSource(session=session)
    result = source.search()

    assert not result.ok
    assert "JSON" in result.error


def test_search_never_performs_real_network_call(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Es darf im Test kein echter Netzwerkaufruf erfolgen")

    monkeypatch.setattr(requests.Session, "post", fail_if_called)
    session = MagicMock()
    session.post.return_value = make_response(json_data={"elements": []})

    source = OverpassSource(session=session)
    result = source.search()

    assert result.ok
