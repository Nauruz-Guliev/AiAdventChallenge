from app.application.citation import extract_citations
from app.domain.models import Hit


def _hit(cid, text):
    return Hit(chunk_id=cid, source="d", title="T", section="s", score=0.5, text=text)


def test_extract_grounded_quote():
    hits = [_hit("c0", "Kotlin Multiplatform shares code across platforms.")]
    cits = extract_citations("It shares code across platforms. [1]", hits)
    assert cits[0].ref == 1 and cits[0].grounded is True
