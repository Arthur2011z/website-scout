from analysis.extractor import extract_page_info

SAMPLE_HTML = """
<html>
<head>
    <title>Beispiel Handwerksbetrieb Hamburg</title>
    <meta name="description" content="Wir bauen und reparieren in Hamburg.">
</head>
<body>
    <p>Willkommen auf unserer Seite.</p>
    <a href="/impressum">Impressum</a>
    <a href="/kontakt">Kontakt</a>
</body>
</html>
"""


def test_extract_page_info_reads_title_and_meta():
    info = extract_page_info(SAMPLE_HTML, "https://beispiel.example")

    assert info.title == "Beispiel Handwerksbetrieb Hamburg"
    assert "Hamburg" in info.meta_description
    assert info.text_length > 0
    assert info.has_impressum is True
    assert "/kontakt" in info.links


def test_extract_page_info_without_impressum():
    html = "<html><head><title>Ohne Impressum</title></head><body>Text</body></html>"
    info = extract_page_info(html, "https://beispiel.example")

    assert info.has_impressum is False
