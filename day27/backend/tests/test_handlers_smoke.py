from aiogram import Router

from app.application.chat_service import ChatService
from app.infrastructure.chat_store import JsonChatStore
from app.presentation.handlers import build_router


def test_build_router(tmp_path, fake_llm, settings):
    service = ChatService(JsonChatStore(tmp_path), fake_llm, settings)
    router = build_router(service, fake_llm, settings)
    assert isinstance(router, Router)
