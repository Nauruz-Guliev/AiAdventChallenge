from app.application.formatter import footer, md_to_telegram_html, split_message
from app.domain.models import GenerationStats


def test_escapes_html():
    assert "&lt;b&gt;" in md_to_telegram_html("<b>")
    assert "&amp;" in md_to_telegram_html("a & b")


def test_inline_code_and_bold():
    out = md_to_telegram_html("use `x=1` and **bold**")
    assert "<code>x=1</code>" in out
    assert "<b>bold</b>" in out


def test_code_block():
    out = md_to_telegram_html("```python\nprint('<hi>')\n```")
    assert "<pre><code>" in out
    assert "print('&lt;hi&gt;')" in out


def test_split_short_is_single():
    assert split_message("hello") == ["hello"]


def test_split_long_preserves_all_chars():
    text = " ".join(["word"] * 3000)
    parts = split_message(text, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert " ".join(parts).split() == text.split()


def test_split_does_not_cut_inside_tag():
    html = "<p>" + ("x" * 50) + "</p>" + ("<p>" + "y" * 50 + "</p>") * 30
    parts = split_message(html, limit=120)
    for p in parts:
        assert not p.rstrip().endswith("<")
        assert p.count("<p>") == p.count("</p>")


def test_footer_with_and_without_stats():
    assert "локально" in footer(None, "gemma4:12b")
    s = GenerationStats(model="gemma4:12b", completion_tokens=40, eval_duration_ns=1_000_000_000)
    assert "40 tok/s" in footer(s, "gemma4:12b")
