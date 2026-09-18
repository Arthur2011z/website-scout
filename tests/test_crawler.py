from unittest.mock import MagicMock

import requests

from crawler.fetcher import Fetcher


def test_fetch_success_returns_html():
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, text="<html>ok</html>")

    fetcher = Fetcher(user_agent="TestBot/1.0", rate_limit_seconds=0, session=session)
    result = fetcher.fetch("https://example.test")

    assert result.ok
    assert result.status_code == 200
    assert "ok" in result.html
    session.get.assert_called_once()
    _, kwargs = session.get.call_args
    assert kwargs["headers"]["User-Agent"] == "TestBot/1.0"


def test_fetch_handles_request_exception():
    session = MagicMock()
    session.get.side_effect = requests.RequestException("boom")

    fetcher = Fetcher(user_agent="TestBot/1.0", rate_limit_seconds=0, session=session)
    result = fetcher.fetch("https://example.test")

    assert not result.ok
    assert result.status_code is None
    assert result.error == "boom"


def test_rate_limit_waits_between_requests(monkeypatch):
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, text="<html></html>")

    sleep_calls = []
    monkeypatch.setattr("crawler.fetcher.time.sleep", lambda s: sleep_calls.append(s))

    # Reihenfolge der monotonic()-Aufrufe je fetch(): start, ende. Vor dem
    # zweiten fetch() zusätzlich ein Aufruf für das Rate-Limit.
    times = iter([100.0, 100.0, 100.5, 100.5, 100.5])
    monkeypatch.setattr("crawler.fetcher.time.monotonic", lambda: next(times))

    fetcher = Fetcher(user_agent="TestBot/1.0", rate_limit_seconds=2.0, session=session)
    fetcher.fetch("https://example.test/1")
    fetcher.fetch("https://example.test/2")

    assert sleep_calls == [1.5]


def test_fetch_measures_response_time_and_final_url():
    session = MagicMock()
    session.get.return_value = MagicMock(
        status_code=200, text="<html>ok</html>", url="https://example.test/redirected"
    )

    fetcher = Fetcher(user_agent="TestBot/1.0", rate_limit_seconds=0, session=session)
    result = fetcher.fetch("http://example.test")

    assert result.final_url == "https://example.test/redirected"
    assert result.response_time_seconds is not None
    assert result.response_time_seconds >= 0.0


def test_fetch_measures_response_time_on_error():
    session = MagicMock()
    session.get.side_effect = requests.RequestException("boom")

    fetcher = Fetcher(user_agent="TestBot/1.0", rate_limit_seconds=0, session=session)
    result = fetcher.fetch("https://example.test")

    assert result.response_time_seconds is not None
    assert result.response_time_seconds >= 0.0


def test_fetch_blocked_by_robots_skips_request():
    session = MagicMock()
    robots_checker = MagicMock()
    robots_checker.is_allowed.return_value = False

    fetcher = Fetcher(
        user_agent="TestBot/1.0",
        rate_limit_seconds=0,
        session=session,
        robots_checker=robots_checker,
    )
    result = fetcher.fetch("https://example.test/disallowed")

    robots_checker.is_allowed.assert_called_once_with("https://example.test/disallowed")
    session.get.assert_not_called()
    assert not result.ok
    assert result.status_code is None
    assert result.html is None
    assert "robots.txt" in result.error


def test_fetch_allowed_by_robots_performs_request():
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, text="<html>ok</html>")
    robots_checker = MagicMock()
    robots_checker.is_allowed.return_value = True

    fetcher = Fetcher(
        user_agent="TestBot/1.0",
        rate_limit_seconds=0,
        session=session,
        robots_checker=robots_checker,
    )
    result = fetcher.fetch("https://example.test/allowed")

    robots_checker.is_allowed.assert_called_once_with("https://example.test/allowed")
    session.get.assert_called_once()
    assert result.ok
