from app.application.citation import extract_citations, lcs, parse_markers
from app.domain.models import Hit


def _hit(cid, text):
    return Hit(cid, f"docs/{cid}.md", "T", "S", 0.9, text)


def test_parse_markers_ordered_unique():
    assert parse_markers("Смотри [2] и [1], ещё раз [2].") == [2, 1]


def test_parse_markers_ignores_zero_and_missing():
    assert parse_markers("нет маркеров [0] [abc]") == []


def test_lcs_finds_longest_common_substring():
    assert lcs("abcXYZdef", "qwXYZzz") == "XYZ"


def test_extract_citations_grounds_long_quote():
    hits = [_hit("c1", "expect и actual declarations это механизм KMP")]
    text = "Ответ: expect и actual declarations это механизм KMP [1]"
    citations = extract_citations(text, hits, min_quote_len=10)
    assert len(citations) == 1
    assert citations[0].ref == 1
    assert citations[0].chunk_id == "c1"
    assert citations[0].grounded is True


def test_extract_citations_flags_short_quote():
    hits = [_hit("c1", "про Ktor client нужно читать документацию")]
    text = "Кратко: Ktor [1]"
    citations = extract_citations(text, hits, min_quote_len=10)
    assert citations[0].grounded is False


def test_extract_citations_skips_out_of_range_ref():
    hits = [_hit("c1", "alpha beta gamma delta epsilon")]
    text = "Смотри [5] тут"
    assert extract_citations(text, hits) == []
