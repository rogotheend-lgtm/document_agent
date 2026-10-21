from backend.report_store import list_reports, search_report, tokenize


def test_demo_reports_are_available():
    report_ids = {report["id"] for report in list_reports()}
    assert {
        "sample-semiconductor-2026",
        "sample-game-2026",
        "sample-battery-2026",
    } <= report_ids


def test_relevant_risk_section_is_found():
    sources = search_report("sample-semiconductor-2026", "주요 리스크", 3)
    assert sources
    assert any(source["section"] == "주요 위험" for source in sources)


def test_unrelated_topic_returns_no_evidence():
    sources = search_report("sample-semiconductor-2026", "게임 섹터 전망", 3)
    assert sources == []


def test_personal_question_does_not_match_common_single_character():
    sources = search_report(
        "sample-game-2026",
        "김서영은 주제를 언제 정할 수 있을까?",
        3,
    )
    assert sources == []


def test_unknown_report_returns_no_evidence():
    assert search_report("missing", "주요 위험", 3) == []


def test_synonyms_are_normalized():
    assert "위험" in tokenize("핵심 리스크")
    assert "위험" in tokenize("위험요인")
    assert "위험" in tokenize("리스크는")
    assert "위험" in tokenize("위험요인을")
    assert "수" not in tokenize("할 수 있을까")
