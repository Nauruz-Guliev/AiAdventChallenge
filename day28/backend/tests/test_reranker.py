from app.domain.models import Hit
from app.infrastructure.heuristic_reranker import HeuristicReranker, filter_by_threshold


def _hit(cid, text, score, section="s"):
    return Hit(chunk_id=cid, source="d", title="T", section=section, score=score, text=text)


def test_rerank_prefers_lexical_overlap():
    hits = [_hit("a", "unrelated text", 0.9), _hit("b", "expect act declarations", 0.8)]
    ranked = HeuristicReranker().rerank("expect declarations", hits)
    assert ranked[0].chunk_id == "b"


def test_filter_threshold_keeps_original_if_all_below():
    hits = [_hit("a", "x", 0.1), _hit("b", "y", 0.2)]
    assert len(filter_by_threshold(hits, min_sim=0.5, k_post=1)) == 1
