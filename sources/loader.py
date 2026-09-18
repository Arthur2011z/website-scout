"""Laden von Start-Quellen (Seed-URLs) für den Website Scout."""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

import yaml


@dataclass
class Source:
    name: str
    url: str
    city: str = ""


def load_sources(path: Union[str, Path]) -> List[Source]:
    """Liest eine YAML-Datei mit einer Liste von Start-Quellen ein."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    sources = []
    for entry in data.get("sources", []):
        sources.append(
            Source(
                name=entry["name"],
                url=entry["url"],
                city=entry.get("city", ""),
            )
        )
    return sources
