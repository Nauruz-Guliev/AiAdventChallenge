from app.presentation.keyboards import answer_keyboard


def test_answer_keyboard_callbacks():
    kb = answer_keyboard(rag_enabled=True)
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert set(datas) == {"cloud", "compare", "eval", "toggle_rag"}


def test_toggle_label_reflects_state():
    on = answer_keyboard(rag_enabled=True)
    off = answer_keyboard(rag_enabled=False)
    labels_on = [b.text for row in on.inline_keyboard for b in row]
    labels_off = [b.text for row in off.inline_keyboard for b in row]
    assert any("выкл" in t.lower() for t in labels_on)
    assert any("вкл" in t.lower() for t in labels_off)
