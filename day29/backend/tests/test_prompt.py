from app.application.prompt import build_context, build_messages
from app.domain.models import Hit, Role


def _hit(cid, section, text):
    return Hit(chunk_id=cid, source="doc.md", title="T", section=section, score=0.5, text=text)


def test_build_context_numbers_blocks():
    ctx = build_context([_hit("c0", "S1", "one"), _hit("c1", "S2", "two")])
    assert "[1] doc.md :: S1" in ctx and "[2] doc.md :: S2" in ctx


def test_build_messages_with_and_without_context():
    with_ctx = build_messages([], "CTX", "Q?")
    assert with_ctx[0].role == Role.SYSTEM
    assert "Контекст:\nCTX" in with_ctx[-1].content and "Вопрос: Q?" in with_ctx[-1].content
    without = build_messages([], "", "Q?")
    assert without[-1].content == "Q?"
