from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def answer_keyboard(rag_enabled: bool) -> InlineKeyboardMarkup:
    rag_label = "🔄 RAG: выкл" if rag_enabled else "🔄 RAG: вкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Профиль", callback_data="profile"),
                InlineKeyboardButton(text="🔀 Квант", callback_data="quant"),
            ],
            [
                InlineKeyboardButton(text="📊 A/B", callback_data="ab"),
                InlineKeyboardButton(text="🧪 Оценка", callback_data="eval"),
            ],
            [
                InlineKeyboardButton(text="☁️ Облако", callback_data="cloud"),
                InlineKeyboardButton(text=rag_label, callback_data="toggle_rag"),
            ],
        ]
    )
