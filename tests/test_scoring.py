from analysis.extractor import PageInfo
from scoring.scorer import DEFAULT_WEIGHTS, ScoreResult, score_page


def _full_page_info() -> PageInfo:
    return PageInfo(
        url="https://beispiel.example",
        title="Titel",
        meta_description="Beschreibung",
        text_length=100,
        has_impressum=True,
        has_viewport=True,
        has_kontakt_link=True,
        emails=["info@beispiel.example"],
        phones=["+49 40 1234567"],
    )


def test_score_page_full_points():
    info = _full_page_info()

    result = score_page(
        info,
        status_code=200,
        final_url="https://beispiel.example",
        response_time_seconds=1.0,
    )

    assert isinstance(result, ScoreResult)
    assert result.score == sum(DEFAULT_WEIGHTS.values())
    assert len(result.explanations) == len(DEFAULT_WEIGHTS)


def test_score_page_no_signals():
    info = PageInfo(url="http://beispiel.example")

    result = score_page(info, status_code=500, final_url="http://beispiel.example", response_time_seconds=10.0)

    assert result.score == 0.0
    assert all("0 Punkte" in explanation for explanation in result.explanations)


def test_score_page_custom_weights():
    info = PageInfo(url="https://beispiel.example", title="Titel")

    result = score_page(info, weights={"has_title": 5.0})

    assert result.score == 5.0


def test_score_page_without_optional_fetch_data_skips_status_and_response_time():
    info = PageInfo(url="https://beispiel.example", title="Titel")

    result = score_page(info)

    assert any("HTTP-Status unbekannt" in e for e in result.explanations)
    assert any("Antwortzeit unbekannt" in e for e in result.explanations)
    # Nur https wird ohne explizite Angabe aus page_info.url abgeleitet.
    assert any("HTTPS" in e for e in result.explanations)


def test_score_page_https_detected_from_final_url_over_original_url():
    info = PageInfo(url="http://beispiel.example", title="Titel")

    result = score_page(info, final_url="https://beispiel.example/")

    assert any("ist über HTTPS erreichbar" in e for e in result.explanations)


def test_score_page_response_time_threshold_is_configurable():
    info = PageInfo(url="https://beispiel.example")

    slow_result = score_page(
        info, weights={"response_time_ok": 2.0}, response_time_seconds=5.0, max_response_time_seconds=4.0
    )
    fast_result = score_page(
        info, weights={"response_time_ok": 2.0}, response_time_seconds=3.0, max_response_time_seconds=4.0
    )

    assert slow_result.score == 0.0
    assert fast_result.score == 2.0


def test_score_page_kontakt_recognises_email_and_phone_without_link():
    info = PageInfo(url="https://beispiel.example", emails=["info@beispiel.example"])

    result = score_page(info, weights={"has_kontakt": 3.0})

    assert result.score == 3.0
