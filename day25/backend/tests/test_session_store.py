import pytest

from app.domain.models import Message, SessionNotFound
from app.infrastructure.session_store import SessionStore


def test_create_get_and_persist(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("цель")
    assert store.get(session.id).memory.goal == "цель"
    again = SessionStore(tmp_path)
    assert again.get(session.id).id == session.id


def test_list_returns_summaries(tmp_path):
    store = SessionStore(tmp_path)
    store.create("goal one")
    store.create("goal two")
    summaries = store.list()
    assert len(summaries) == 2
    assert {s["goal"] for s in summaries} == {"goal one", "goal two"}


def test_get_missing_raises(tmp_path):
    with pytest.raises(SessionNotFound):
        SessionStore(tmp_path).get("nope")


def test_append_message_saves(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("цель")
    store.append_message(session, Message(role="user", text="q"))
    assert len(store.get(session.id).messages) == 1
