from app.domain.models import Hit
from app.infrastructure.heuristic_reranker import (
    HeuristicReranker,
    filter_by_threshold,
    tokenize,
)


def _hit(cid, text, score, title="", section=""):
    return Hit(chunk_id=cid, source="f.md", title=title, section=section, score=score, text=text)


def test_tokenize_filters_short_and_keeps_alnum():
    assert tokenize("Ktor client, iOS!") == {"ktor", "client", "ios"}


def test_rerank_boosts_lexical_overlap():
    hits = [
        _hit("a", "unrelated content", 0.9),
        _hit("b", "use ktor client for networking", 0.5),
    ]
    out = HeuristicReranker(0.6, 0.3, 0.1).rerank("ktor client", hits)
    assert out[0].chunk_id == "b"


def test_rerank_head_bonus():
    hits = [
        _hit("a", "body text without term", 0.5),
        _hit("b", "body text without term", 0.5, section="Ktor setup"),
    ]
    out = HeuristicReranker(0.6, 0.3, 0.1).rerank("ktor", hits)
    assert out[0].chunk_id == "b"


def test_filter_drops_below_threshold_and_caps():
    hits = [_hit(str(i), "t", 0.9 - i * 0.1) for i in range(5)]
    out = filter_by_threshold(hits, min_sim=0.55, k_post=8)
    assert [h.chunk_id for h in out] == ["0", "1", "2", "3"]


def test_filter_fallback_when_all_below():
    hits = [_hit("a", "t", 0.1), _hit("b", "t", 0.05)]
    out = filter_by_threshold(hits, min_sim=0.9, k_post=8)
    assert [h.chunk_id for h in out] == ["a", "b"]
