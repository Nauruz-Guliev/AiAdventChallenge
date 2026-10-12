from app.application.formatter import md_to_telegram_html, split_message


def test_no_unsupported_tags():
    out = md_to_telegram_html("Привет\n\n**жирный** и `код`")
    assert "<p>" not in out and "</p>" not in out and "<br" not in out
    assert "<b>жирный</b>" in out and "<code>код</code>" in out


def test_escaping_and_code_block():
    out = md_to_telegram_html("a < b & c\n\n```py\nx = 1 < 2\n```")
    assert "a &lt; b &amp; c" in out
    assert "<pre><code>x = 1 &lt; 2</code></pre>" in out


def test_link_heading_strike():
    out = md_to_telegram_html("# Итог\n~~старое~~ [доки](https://kotlinlang.org)")
    assert "<b>Итог</b>" in out and "<s>старое</s>" in out
    assert '<a href="https://kotlinlang.org">доки</a>' in out


def test_markers_inside_code_not_formatted():
    out = md_to_telegram_html("`**not bold**`")
    assert "<code>**not bold**</code>" in out and "<b>" not in out


def test_partial_stream_is_valid_html():
    out = md_to_telegram_html("текст **полу")
    assert "<b>" not in out


def test_split_message_respects_limit():
    parts = split_message("x" * 100, limit=40)
    assert len(parts) == 3 and all(len(p) <= 40 for p in parts)
