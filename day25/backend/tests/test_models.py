from app.domain.models import Citation, Hit, Message, Session, TaskMemory


def test_hit_and_citation_fields():
    hit = Hit("c1", "docs/a.md", "A", "Intro", 0.9, "text")
    cit = Citation(1, "c1", "docs/a.md", "Intro", "alpha", True)
    assert hit.source == "docs/a.md"
    assert hit.score == 0.9
    assert cit.grounded is True


def test_session_roundtrip():
    session = Session(id="s1", memory=TaskMemory(goal="цель", constraints=["c"]))
    session.messages.append(Message(role="user", text="q"))
    session.messages.append(Message(
        role="assistant", text="a",
        sources=[Hit("c1", "docs/a.md", "A", "I", 0.9, "t")],
        citations=[Citation(1, "c1", "docs/a.md", "I", "t", True)],
    ))
    restored = Session.from_dict(session.to_dict())
    assert restored.id == "s1"
    assert restored.memory.goal == "цель"
    assert restored.memory.constraints == ["c"]
    assert restored.messages[1].sources[0].chunk_id == "c1"
    assert restored.messages[1].citations[0].grounded is True


def test_task_memory_from_dict_drops_blanks():
    m = TaskMemory.from_dict({"goal": " ", "clarifications": ["a", "", "b"]})
    assert m.goal == ""
    assert m.clarifications == ["a", "b"]
