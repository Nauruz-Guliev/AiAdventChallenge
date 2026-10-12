from __future__ import annotations

from app.domain.models import ABReport, EvalReport, Quant, RagAnswer, OptimizationProfile

START_TEXT = (
    "🧪 Я — <b>оптимизированный</b> локальный RAG-ассистент по Kotlin Multiplatform.\n"
    "Поиск по базе KMP и ответ делает <b>твоя</b> модель на этом компьютере "
    "(<code>{model}</code> через Ollama). Облако для обычных ответов не используется.\n\n"
    "• задай вопрос — получишь ответ <b>с источниками</b>;\n"
    "• профиль, квант и A/B «до/после» — кнопками под ответом;\n"
    "• /help — все команды."
)

HELP_TEXT = (
    "Команды:\n"
    "/profile — активный профиль оптимизации\n"
    "/profile baseline|params|optimized — переключить\n"
    "/quant q4|q8 — переключить квант модели\n"
    "/ab — быстрый A/B (3 вопроса × 1)\n"
    "/ab full — полный A/B (10 вопросов × 2)\n"
    "/eval — локально vs облако (RAG)\n"
    "/rag · /norag — поиск по базе вкл/выкл\n"
    "/think on|off — показывать «размышления»\n"
    "/status — модель, квант, профиль, индекс\n"
    "/new — очистить историю · /id — id чата\n"
    "Кнопки: ⚙️ Профиль · 🔀 Квант · 📊 A/B · 🧪 Оценка · ☁️ Облако · 🔄 RAG"
)

OFFLINE_TEXT = "⚠️ Локальная модель не отвечает.\nЗапусти Ollama (`ollama serve`), затем повтори."
NO_CLOUD_TEXT = "⚠️ Облачная модель недоступна (нет ключа DEEPSEEK_API_KEY или сеть)."
BUSY_TEXT = "⏳ Я ещё работаю над предыдущим запросом, подожди немного."
EVAL_BUSY_TEXT = "⏳ Прогон оценки уже идёт."
EVAL_STARTED_TEXT = "🧪 Запускаю /eval: 10 вопросов × {runs} × 3 режима. Это несколько минут…"
AB_BUSY_TEXT = "⏳ A/B уже идёт, подожди."
AB_STARTED_TEXT = "📊 Запускаю A/B ({mode}): {questions} вопросов × {runs}. Это может занять время…"


def _fmt_quality(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def _fmt_tps(v: float) -> str:
    return "—" if v <= 0 else f"{v:.0f}"


def sources_text(answer: RagAnswer) -> str:
    if not answer.sources:
        if answer.answerable:
            return "🔎 Поиск по базе не использовался (режим без RAG)."
        return f"🔎 Релевантность слишком низкая (score={answer.relevance})."
    lines = ["📚 <b>Источники</b>"]
    for i, h in enumerate(answer.sources, 1):
        lines.append(f"[{i}] {h.source} :: {h.section}  ({h.score:.2f})")
    grounded = [c for c in answer.citations if c.grounded]
    if grounded:
        lines.append("")
        lines.append("🔖 <b>Цитаты</b>")
        for c in grounded[:3]:
            lines.append(f"[{c.ref}] «{c.quote[:200]}»")
    return "\n".join(lines)


def eval_report_text(report: EvalReport) -> str:
    lines = [
        "📊 <b>Сравнение локальной и облачной модели (RAG по KMP)</b>",
        f"Вопросов: {report.questions} · прогонов на вопрос: {report.runs}",
        "",
        "<pre>",
        "режим              кач-во  латентн  tok/s  ошибки",
    ]
    for r in report.rows:
        tps = _fmt_tps(r.tokens_per_second)
        lines.append(
            f"{r.label:<18} {r.quality_mean:>5.2f}  {r.latency_mean_ms:>6.0f}  {tps:>5}  "
            f"{r.error_rate * 100:>4.0f}%"
        )
    lines.append("</pre>")
    lines.append("Судья — облачная модель, оценка слепая (не знает, какая модель отвечала).")
    return "\n".join(lines)


def _ab_row(c) -> str:
    mem = f"{c.resources.model_size_gb:.1f}ГБ"
    return (
        f"{c.profile:<10} {c.quant:<6} {_fmt_quality(c.quality_mean):>5}  "
        f"{c.latency_mean_ms:>6.0f}  {_fmt_tps(c.tokens_per_second):>5}  "
        f"{c.prompt_tokens:>6.0f}  {mem:>6}"
    )


def ab_report_text(report: ABReport) -> str:
    mode = "быстрый" if report.quick else "полный"
    lines = [
        "📊 <b>A/B: локальная LLM на RAG по KMP</b>",
        f"Вопросов: {report.questions} · прогонов: {report.runs} · режим: {mode}",
        "",
        "<pre>",
        "профиль    квант   кач-во  латентн  tok/s  промпт  размер",
    ]
    for c in report.cells:
        lines.append(_ab_row(c))
    lines.append("</pre>")

    for quant in ("q4", "q8"):
        cells = {c.profile: c for c in report.cells if c.quant == quant}
        base, opt = cells.get("baseline"), cells.get("optimized")
        if base and opt and base.quality_mean is not None and opt.quality_mean is not None:
            dq = opt.quality_mean - base.quality_mean
            dl = opt.latency_mean_ms - base.latency_mean_ms
            lines.append(
                f"Δ optimized vs baseline ({quant.upper()}): качество {dq:+.2f} · "
                f"латентность {dl:+.0f} мс · tok/s {_fmt_tps(opt.tokens_per_second)}"
            )

    q4 = next((c for c in report.cells if c.quant == "q4" and c.profile == "optimized"), None)
    q8 = next((c for c in report.cells if c.quant == "q8" and c.profile == "optimized"), None)
    if q4 and q8 and q4.quality_mean is not None and q8.quality_mean is not None:
        lines.append(
            f"Δ Q8_0 vs Q4_K_M (optimized): качество {q8.quality_mean - q4.quality_mean:+.2f} · "
            f"латентность {q8.latency_mean_ms - q4.latency_mean_ms:+.0f} мс · "
            f"размер {q8.resources.model_size_gb:.1f} vs {q4.resources.model_size_gb:.1f} ГБ"
        )

    for note in report.notes:
        lines.append(f"ℹ️ {note}")
    lines.append("Судья — deepseek-chat, оценка слепая (не знает профиль/квант).")
    return "\n".join(lines)


def profile_text(profile: OptimizationProfile, quant: Quant) -> str:
    opts = profile.options
    keys = ["num_ctx", "temperature", "top_p", "top_k", "num_predict", "repeat_penalty"]
    lines = [f"⚙️ <b>Активный профиль: {profile.label}</b>", "<pre>"]
    for k in keys:
        lines.append(f"{k:<15} {opts.get(k, '—')}")
    lines.append(f"{'think':<15} {str(profile.think).lower()}")
    lines.append(f"{'промпт':<15} {profile.prompt}")
    lines.append("</pre>")
    lines.append(f"Модель: <b>{quant.label}</b> (<code>{quant.model}</code>)")
    return "\n".join(lines)


def quant_text(quant: Quant, size_gb: float, vram_gb: float) -> str:
    return (
        f"🔀 <b>Квант: {quant.label}</b>\n"
        f"Модель: <code>{quant.model}</code>\n"
        f"Размер на диске: {size_gb:.1f} ГБ · в памяти: {vram_gb:.1f} ГБ"
    )


def status_text(
    *,
    profile_label: str,
    quant: Quant,
    index_path: str,
    embedder: str,
    rag_enabled: bool,
    cloud: bool,
    vram_gb: float = 0.0,
) -> str:
    mem = f" · память {vram_gb:.1f} ГБ" if vram_gb > 0 else ""
    return (
        "📟 <b>Состояние</b>\n"
        f"Профиль: <b>{profile_label}</b>\n"
        f"Квант: <b>{quant.label}</b> (<code>{quant.model}</code>){mem}\n"
        f"Индекс: <code>{index_path}</code>\n"
        f"Эмбеддер: <code>{embedder}</code>\n"
        f"Режим: {'RAG (поиск по базе)' if rag_enabled else 'без RAG'}\n"
        f"Облако: {'доступно' if cloud else 'нет ключа'}"
    )
