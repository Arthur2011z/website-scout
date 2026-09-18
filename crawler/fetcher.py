"""Einfacher HTTP-Crawler mit Rate-Limit und festem User-Agent."""
from dataclasses import dataclass
from typing import Optional
import time

import requests

from crawler.robots import RobotsChecker


@dataclass
class FetchResult:
    url: str
    status_code: Optional[int]
    html: Optional[str]
    error: Optional[str] = None
    # Tatsächlich abgerufene Adresse (kann sich z. B. durch eine
    # HTTP->HTTPS-Weiterleitung vom angefragten `url` unterscheiden).
    final_url: str = ""
    # Gemessene Antwortzeit in Sekunden, für die Prüfung "Antwortzeit".
    response_time_seconds: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code == 200


class Fetcher:
    """Holt HTML-Seiten ab und hält dabei ein Mindest-Zeitintervall zwischen Anfragen ein."""

    def __init__(
        self,
        user_agent: str,
        rate_limit_seconds: float = 2.0,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
        robots_checker: Optional[RobotsChecker] = None,
    ):
        self.user_agent = user_agent
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.robots_checker = robots_checker
        self._last_request_time: Optional[float] = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_time is None:
            return
        elapsed = time.monotonic() - self._last_request_time
        remaining = self.rate_limit_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def fetch(self, url: str) -> FetchResult:
        if self.robots_checker is not None and not self.robots_checker.is_allowed(url):
            return FetchResult(
                url=url,
                status_code=None,
                html=None,
                error=f"Abruf durch robots.txt untersagt: {url}",
            )

        self._wait_for_rate_limit()
        headers = {"User-Agent": self.user_agent}
        start = time.monotonic()
        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout_seconds)
            now = time.monotonic()
            self._last_request_time = now
            return FetchResult(
                url=url,
                status_code=response.status_code,
                html=response.text,
                final_url=getattr(response, "url", "") or "",
                response_time_seconds=now - start,
            )
        except requests.RequestException as exc:
            now = time.monotonic()
            self._last_request_time = now
            return FetchResult(
                url=url,
                status_code=None,
                html=None,
                error=str(exc),
                response_time_seconds=now - start,
            )
