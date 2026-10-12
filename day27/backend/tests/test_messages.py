from app.presentation import messages


def test_start_text_mentions_local_and_model():
    t = messages.START_TEXT.format(model="gemma4:12b", base_url="http://localhost:11434")
    assert "gemma4:12b" in t
    assert "локаль" in t.lower()
    assert "localhost:11434" in t


def test_offline_text_is_friendly():
    t = messages.OFFLINE_TEXT.lower()
    assert "не отвечает" in t or "запусти" in t
