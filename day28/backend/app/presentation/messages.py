from __future__ import annotations

from app.domain.models import EvalReport, RagAnswer

START_TEXT = (
    "📚 Я — <b>локальный</b> RAG-ассистент по Kotlin Multiplatform.\n"
    "Поиск по базе и ответ делает <b>твоя</b> модель на этом компьютере "
    "(<code>{model}</code> через Ollama). Облако для обычных ответов не используется.\n\n"
    "• задай вопрос — получишь ответ <b>с источниками</b>;\n"
    "• кнопки под ответом: облачная модель, сравнение, прогон оценки;\n"
    "• /norag — отвечать без поиска, /help — все команды."
)

HELP_TEXT = (
    "Команды:\n"
    "/new, /reset — очистить историю\n"
    "/rag — отвечать с поиском по базе (по умолчанию)\n"
    "/norag — отвечать без поиска\n"
    "/compare &lt;вопрос&gt; — локальный и облачный ответ рядом\n"
    "/eval [N] — прогон 10 вопросов × N (по умолчанию 3): качество/скорость/стабильность\n"
    "/think on|off — показывать «размышления» модели\n"
    "/status — состояние (модель, индекс, режим)\n"
    "/id — id чата\n"
    "Кнопки под ответом: ☁️ Облако · ⚖️ Сравнить · 🧪 Прогон · 🔄 RAG вкл/выкл"
)

OFFLINE_TEXT = (
    "⚠️ Локальная модель не отвечает.\n"
    "Запусти Ollama (`ollama serve`), затем повтори."
)

NO_CLOUD_TEXT = "⚠️ Облачная модель недоступна (нет ключа DEEPSEEK_API_KEY или сеть)."
BUSY_TEXT = "⏳ Я ещё работаю над предыдущим запросом, подожди немного."
EVAL_BUSY_TEXT = "⏳ Прогон оценки уже идёт."
EVAL_STARTED_TEXT = "🧪 Запускаю прогон: 10 вопросов × {runs} × 3 режима. Это несколько минут…"


def sources_text(answer: RagAnswer) -> str:
    if not answer.sources:
        if answer.answerable:
            return "🔎 Поиск по базе не использовался (режим без RAG)."
        return f"🔎 Релевантность слишком низкая (score={answer.relevance})."
    lines = ["📚 Источники:"]
    for i, h in enumerate(answer.sources, 1):
        lines.append(f"[{i}] {h.source} :: {h.section}  ({h.score:.2f})")
    grounded = [c for c in answer.citations if c.grounded]
    if grounded:
        lines.append("\n🔖 Цитаты:")
        for c in grounded[:3]:
            lines.append(f"[{c.ref}] «{c.quote[:200]}»")
    return "\n".join(lines)


def eval_report_text(report: EvalReport) -> str:
    lines = [
        "📊 Сравнение локальной и облачной модели (RAG по KMP)",
        f"Вопросов: {report.questions} · прогонов на вопрос: {report.runs}",
        "",
        "| Режим | Качество (0..1) | Скорость | Стабильность | Ошибки |",
        "|---|---|---|---|---|",
    ]
    for r in report.rows:
        speed = f"{r.latency_mean_ms:.0f} мс"
        if r.tokens_per_second > 0:
            speed += f" · {r.tokens_per_second:.0f} tok/s"
        stab = f"σ балла {r.quality_std:.2f}, σ времени {r.latency_std_ms:.0f} мс"
        lines.append(
            f"| {r.label} | {r.quality_mean:.2f} | {speed} | {stab} | {r.error_rate * 100:.0f}% |"
        )
    lines.append("")
    lines.append("Судья — облачная модель, оценка слепая (не знает, какая модель отвечала).")
    return "\n".join(lines)
