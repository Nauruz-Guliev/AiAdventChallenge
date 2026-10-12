from app.application.prompt import OPTIMIZED_SYSTEM, PROMPTS, build_context, build_messages
from app.domain.models import Hit, Role


def test_two_prompts_registered():
    assert set(PROMPTS) == {"baseline", "optimized"}
    assert "Не нашёл в базе" in OPTIMIZED_SYSTEM


def test_build_context_numbers_blocks():
    hits = [Hit("c0", "doc.md", "T", "S1", 0.5, "one"), Hit("c1", "doc.md", "T", "S2", 0.5, "two")]
    ctx = build_context(hits)
    assert "[1] doc.md :: S1" in ctx and "[2] doc.md :: S2" in ctx


def test_build_messages_uses_prompt_key():
    msgs = build_messages([], "CTX", "Q?", prompt_key="optimized")
    assert msgs[0].role == Role.SYSTEM and msgs[0].content == OPTIMIZED_SYSTEM
    assert "Контекст:\nCTX" in msgs[-1].content and "Вопрос: Q?" in msgs[-1].content
    assert build_messages([], "", "Q?", prompt_key="baseline")[-1].content == "Q?"
