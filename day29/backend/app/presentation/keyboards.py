from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def answer_keyboard(rag_enabled: bool) -> InlineKeyboardMarkup:
    rag_label = "🔄 RAG: выкл" if rag_enabled else "🔄 RAG: вкл"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☁️ Облако", callback_data="cloud"),
            InlineKeyboardButton(text="⚖️ Сравнить", callback_data="compare"),
        ],
        [
            InlineKeyboardButton(text="🧪 Прогон 10 вопросов", callback_data="eval"),
            InlineKeyboardButton(text=rag_label, callback_data="toggle_rag"),
        ],
    ])
