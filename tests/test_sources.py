from sources.loader import load_sources


def test_load_sources_reads_entries(tmp_path):
    seed_file = tmp_path / "seed.yaml"
    seed_file.write_text(
        "sources:\n"
        '  - name: "Beispiel Handwerksbetrieb"\n'
        '    url: "https://beispiel-handwerk.example"\n'
        '    city: "Hamburg"\n',
        encoding="utf-8",
    )

    sources = load_sources(seed_file)

    assert len(sources) == 1
    assert sources[0].name == "Beispiel Handwerksbetrieb"
    assert sources[0].url == "https://beispiel-handwerk.example"
    assert sources[0].city == "Hamburg"


def test_load_sources_empty_file(tmp_path):
    seed_file = tmp_path / "empty.yaml"
    seed_file.write_text("sources: []", encoding="utf-8")

    sources = load_sources(seed_file)

    assert sources == []
