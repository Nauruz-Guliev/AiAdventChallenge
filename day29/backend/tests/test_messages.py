from app.domain.models import ABReport, CellResult, EvalReport, EvalRow, ResourceSample
from app.presentation.messages import ab_report_text, eval_report_text, sources_text
from app.domain.models import RagAnswer


def _cell(profile, quant, q, lat, tps):
    return CellResult(
        profile, quant, f"{profile} · {quant}", q, 0.05, lat, 100.0, tps, 1980.0, 0.0, 6, False,
        ResourceSample(model_size_gb=8.0, size_vram_gb=5.0),
    )


def test_ab_report_is_pre_with_deltas():
    c1 = _cell("baseline", "q4", 0.79, 3480.0, 109.0)
    c2 = _cell("optimized", "q4", 0.87, 2400.0, 133.0)
    c8 = _cell("optimized", "q8", 0.88, 3300.0, 95.0)
    out = ab_report_text(ABReport((c1, c2, c8), 10, 2, False))
    assert "<pre>" in out and "</pre>" in out
    assert "0.87" in out and "Δ" in out and "Q8_0" in out
    assert "|" not in out


def test_eval_report_is_pre():
    r = EvalRow("Локальная+RAG", 0.8, 0.1, 3000.0, 500.0, 100.0, 0.0, 30)
    out = eval_report_text(EvalReport((r,), 10, 3))
    assert "<pre>" in out and "Локальная+RAG" in out


def test_sources_text_lists_sources():
    from app.domain.models import Hit

    a = RagAnswer(reply="x", sources=(Hit("c0", "doc.md", "T", "S", 0.8, "t"),))
    assert "Источники" in sources_text(a) and "doc.md" in sources_text(a)
