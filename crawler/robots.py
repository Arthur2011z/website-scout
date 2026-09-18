"""Prüft robots.txt einer Domain, bevor eine Seite abgerufen wird.

Der Website Scout ruft ausschließlich einzelne Seiten per GET ab (keine
Formulare, keine Login-Bereiche). Damit auch das robots.txt-Regelwerk
der jeweiligen Domain respektiert wird, wird vor dem eigentlichen Abruf
geprüft, ob der konfigurierte User-Agent die Ziel-URL besuchen darf.

Ist robots.txt selbst nicht erreichbar (Timeout, Verbindungsfehler,
Fehlerstatuscode), wird der Zugriff im Zweifel erlaubt - ein einzelner
Fehler beim robots.txt-Abruf soll den gesamten Lauf nicht stoppen.
"""
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests


class RobotsChecker:
    """Fragt robots.txt pro Domain ab und cached das Ergebnis für die Laufzeit."""

    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self._cache: Dict[str, RobotFileParser] = {}

    def _get_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._cache:
            return self._cache[origin]

        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            response = self.session.get(
                f"{origin}/robots.txt",
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                # Keine robots.txt vorhanden -> laut Standard darf alles abgerufen werden.
                parser.parse([])
            else:
                parser.parse(response.text.splitlines())
        except requests.RequestException:
            # robots.txt nicht erreichbar: im Zweifel erlauben, nicht abstürzen.
            parser.parse([])

        self._cache[origin] = parser
        return parser

    def is_allowed(self, url: str) -> bool:
        """Prüft, ob der konfigurierte User-Agent laut robots.txt auf `url` zugreifen darf."""
        parser = self._get_parser(url)
        return parser.can_fetch(self.user_agent, url)
