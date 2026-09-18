"""Einfache Analyse von HTML-Seiten (noch keine komplexe Inhaltsanalyse)."""
import re
from dataclasses import dataclass, field
from typing import List, Tuple

from bs4 import BeautifulSoup

IMPRESSUM_KEYWORDS = ("impressum",)
KONTAKT_KEYWORDS = ("kontakt", "contact")

# Bewusst einfache, nachvollziehbare Muster für die Kontakt-Prüfung -
# keine vollständige RFC-Validierung, sondern ein plausibler Fund im
# sichtbaren Text bzw. in mailto:/tel:-Links.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+49[\s/\-]?|\b0)[0-9][0-9 /\-()]{5,14}[0-9]")


@dataclass
class PageInfo:
    url: str
    title: str = ""
    meta_description: str = ""
    text_length: int = 0
    has_impressum: bool = False
    has_viewport: bool = False
    has_kontakt_link: bool = False
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)


def _extract_contact_signals(soup: BeautifulSoup, links: List[str]) -> Tuple[bool, List[str], List[str]]:
    """Sucht Kontakt-Links sowie E-Mail-Adressen/Telefonnummern im Text und in Links."""
    text = soup.get_text(separator=" ", strip=True)
    emails = dict.fromkeys(EMAIL_PATTERN.findall(text))
    phones = dict.fromkeys(m.strip() for m in PHONE_PATTERN.findall(text))

    has_kontakt_link = False
    for link in links:
        href = (link or "").strip()
        lower = href.lower()

        if lower.startswith("mailto:"):
            address = href[len("mailto:"):].split("?")[0].strip()
            if address:
                emails[address] = None
        elif lower.startswith("tel:"):
            number = href[len("tel:"):].strip()
            if number:
                phones[number] = None

        if any(keyword in lower for keyword in KONTAKT_KEYWORDS):
            has_kontakt_link = True

    return has_kontakt_link, list(emails), list(phones)


def extract_page_info(html: str, url: str) -> PageInfo:
    """Extrahiert einfache, leicht nachvollziehbare Merkmale aus einer HTML-Seite."""
    soup = BeautifulSoup(html or "", "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "").strip() if meta_tag else ""

    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    has_viewport = viewport_tag is not None

    text_length = len(soup.get_text(separator=" ", strip=True))

    links = [a.get("href") for a in soup.find_all("a", href=True)]

    # Nur tatsächliche Links zählen: Ein Seitentitel wie „Ohne Impressum"
    # darf nicht als vorhandenes Impressum gewertet werden.
    has_impressum = any(
        keyword in (link or "").lower()
        for link in links
        for keyword in IMPRESSUM_KEYWORDS
    )

    has_kontakt_link, emails, phones = _extract_contact_signals(soup, links)

    return PageInfo(
        url=url,
        title=title,
        meta_description=meta_description,
        text_length=text_length,
        has_impressum=has_impressum,
        has_viewport=has_viewport,
        has_kontakt_link=has_kontakt_link,
        emails=emails,
        phones=phones,
        links=links,
    )
