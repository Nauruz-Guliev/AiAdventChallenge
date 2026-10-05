from app.domain.models import Answer, EvalItem, EvalReport, Hit


def test_hit_fields():
    hit = Hit("c1", "docs/a.md", "A", "Intro", 0.9, "text")
    assert hit.source == "docs/a.md"
    assert hit.score == 0.9


def test_answer_holds_mode_text_and_sources():
    hit = Hit("c1", "docs/a.md", "A", "Intro", 0.9, "text")
    answer = Answer(mode="rag_full", text="ok", sources=(hit,))
    assert answer.mode == "rag_full"
    assert answer.sources[0].chunk_id == "c1"


def test_eval_item_and_report():
    item = EvalItem(
        question="q",
        expectation="e",
        sources=["a.md"],
        mode_answers={"rag": "y"},
        mode_scores={"rag": 0.9},
        mode_sources={"rag": ["docs/a.md :: Intro"]},
        source_coverage={"rag": True},
    )
    report = EvalReport(items=[item], summary={"questions": 1})
    assert report.items[0].mode_scores["rag"] == 0.9
    assert report.summary["questions"] == 1
