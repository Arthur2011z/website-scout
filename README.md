# Website Scout

Ein lokales Werkzeug, um Websites (z. B. von Handwerksbetrieben oder
Initiativen in Hamburg) aus einer festen Liste von Start-Quellen sowie
optional über die automatische OpenStreetMap/Overpass-Suche abzurufen,
regelbasiert zu prüfen und in einem verlinkten HTML-Report darzustellen.
Vor dem Abruf wird `robots.txt` berücksichtigt. Der Scout bewertet unter
anderem HTTPS, Statuscode, Antwortzeit, Seitentitel, mobile Viewport-Angabe,
Impressum sowie Kontaktmöglichkeiten.

**Wichtig:** Dies ist bewusst ein einfaches Grundgerüst. Über
`overpass.enabled: true` in `config.yaml` steht bereits eine automatische
Website-Suche für das Gebiet Hamburg über die Overpass-API (OpenStreetMap)
zur Verfügung; die feste Seed-URL-Liste (`sources/seed_urls.yaml`) bleibt
davon unberührt und läuft weiterhin zusätzlich. Es gibt weiterhin
**keine komplexe Inhaltsanalyse**; das ist eine mögliche spätere
Ausbaustufe.

## Projektstruktur

```
website-scout/
├── config.yaml            # Zentrale Konfiguration (Stadt, User-Agent, Rate-Limit, Bewertung)
├── requirements.txt        # Python-Abhängigkeiten
├── main.py                 # Orchestriert Crawling, Analyse, Scoring, Speicherung, Report
├── sources/                # Verwaltung der Start-Quellen (Seed-URLs) und der Overpass-Suche
│   ├── loader.py
│   ├── overpass_source.py
│   └── seed_urls.yaml
├── crawler/                # HTTP-Abruf mit Rate-Limit und User-Agent
│   └── fetcher.py
├── analysis/                # Einfache Extraktion von Titel, Meta-Description, Links etc.
│   └── extractor.py
├── scoring/                 # Regelbasierte Bewertung der extrahierten Merkmale
│   └── scorer.py
├── database/                # SQLite-Anbindung zur Ablage der Ergebnisse
│   └── db.py
├── templates/                # Jinja2-Templates für Übersicht und Detailseiten
│   ├── index.html.j2
│   └── detail.html.j2
└── tests/                     # pytest-Tests für alle Module
```

## Einrichtung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Nutzung

```bash
python3 main.py
```

Dies lädt die Quellen aus `sources/seed_urls.yaml`, ruft sie ab, wertet
sie mit den in `config.yaml` hinterlegten Gewichtungen aus, speichert die
Ergebnisse in `database/website_scout.db` und erzeugt im Ausgabeordner eine
`index.html`-Übersicht sowie eine eigene `website-*.html`-Detailseite pro Fund.

Die mitgelieferte `sources/seed_urls.yaml` enthält nur Platzhalter-URLs
(`*.example`) und muss vor echter Nutzung durch reale, geprüfte Quellen
ersetzt werden.

## Konfiguration (`config.yaml`)

- **region**: Zielregion (aktuell Hamburg).
- **crawler**: User-Agent, Rate-Limit (Sekunden zwischen Anfragen), Timeout,
  maximale Seiten pro Domain.
- **scoring**: Gewichtungen für die einfachen Bewertungsmerkmale sowie ein
  Schwellenwert für "relevant".
- **database** / **output**: Pfade für SQLite-Datenbank und generierte Reports.
- **overpass**: Schalter `enabled`, um zusätzlich Unternehmen mit
  hinterlegter Website-URL über die Overpass-API (OpenStreetMap) für das
  Gebiet `area_name` zu suchen (`limit` begrenzt die Trefferzahl pro
  Anfrage). Die gefundenen Unternehmen werden als weitere Kandidaten in
  denselben Ablauf (Abruf, Bewertung, Speicherung, Report) übernommen; der
  bestehende Seed-URL-Modus (`sources/seed_urls.yaml`) läuft unabhängig
  davon immer mit. Schlägt die Overpass-Anfrage fehl (z. B. Timeout oder
  Fehlerstatuscode), gibt das Programm eine verständliche Meldung aus und
  läuft mit den übrigen Quellen normal weiter.

## Tests ausführen

```bash
pytest
```

Alle Tests laufen offline (kein echter Netzwerkzugriff) und nutzen
Mocks bzw. eine In-Memory-SQLite-Datenbank.
