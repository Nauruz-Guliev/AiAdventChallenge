from app.application.formatter import md_to_telegram_html, split_message


def test_md_to_html_bold_and_code():
    out = md_to_telegram_html("**bold** and `code`")
    assert "<b>bold</b>" in out and "<code>code</code>" in out


def test_split_message_respects_limit():
    text = "x" * 100
    parts = split_message(text, limit=40)
    assert len(parts) == 3 and all(len(p) <= 40 for p in parts)
