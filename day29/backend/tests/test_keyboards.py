from app.presentation.keyboards import answer_keyboard


def test_keyboard_callbacks():
    kb = answer_keyboard(rag_enabled=True)
    data = {b.callback_data for row in kb.inline_keyboard for b in row}
    assert data == {"profile", "quant", "ab", "eval", "cloud", "toggle_rag"}


def test_rag_toggle_label():
    on = [b.text for row in answer_keyboard(True).inline_keyboard for b in row]
    off = [b.text for row in answer_keyboard(False).inline_keyboard for b in row]
    assert any("выкл" in t.lower() for t in on)
    assert any("вкл" in t.lower() for t in off)
