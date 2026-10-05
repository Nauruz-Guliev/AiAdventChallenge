from app.domain.models import Answer, Citation, EvalItem, EvalReport, Hit


def test_hit_fields():
    hit = Hit("c1", "docs/a.md", "A", "Intro", 0.9, "text")
    assert hit.source == "docs/a.md"
    assert hit.score == 0.9


def test_citation_fields():
    c = Citation(ref=1, chunk_id="c1", source="docs/a.md", section="Intro",
                 quote="alpha", grounded=True)
    assert c.ref == 1
    assert c.grounded is True


def test_answer_holds_mode_text_sources_and_citations():
    hit = Hit("c1", "docs/a.md", "A", "Intro", 0.9, "text")
    cit = Citation(1, "c1", "docs/a.md", "Intro", "text", True)
    answer = Answer(mode="rag", text="ok", sources=(hit,), citations=(cit,))
    assert answer.citations[0].chunk_id == "c1"
    assert answer.answerable is True


def test_answer_not_answerable_defaults():
    answer = Answer(mode="rag_guard", text="не знаю", sources=(), answerable=False, relevance=0.1)
    assert answer.answerable is False
    assert answer.relevance == 0.1


def test_eval_item_and_report():
    item = EvalItem(
        question="q", expectation="e", sources=["a.md"],
        mode_answers={"rag": "y"}, mode_scores={"rag": 0.9},
        mode_sources={"rag": ["docs/a.md :: Intro"]}, source_coverage={"rag": True},
        mode_citations={"rag": [{"ref": 1, "quote": "x", "grounded": True}]},
        has_citations={"rag": True}, grounding_rate={"rag": 1.0},
        support_scores={"rag": 0.8}, no_answer={"rag": False},
    )
    report = EvalReport(items=[item], summary={"questions": 1})
    assert report.items[0].grounding_rate["rag"] == 1.0
    assert report.summary["questions"] == 1
