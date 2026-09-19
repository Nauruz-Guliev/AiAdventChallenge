from app.domain.models import (
    PROFILE_LENGTHS,
    PROFILE_STRUCTURES,
    PROFILE_TONES,
    ChatMessage,
    UserProfile,
)

TONE_LABELS = {
    "formal": "деловой",
    "friendly": "дружелюбный",
    "neutral": "нейтральный",
}
LENGTH_LABELS = {
    "short": "короткий",
    "medium": "средний",
    "detailed": "подробный",
}
STRUCTURE_LABELS = {
    "prose": "обычный текст",
    "bullets": "списки",
    "markdown": "markdown",
}
LANGUAGE_LABELS = {
    "ru": "русский",
    "en": "английский",
    "kk": "казахский",
}


def build_profile_block(profile: UserProfile | None) -> ChatMessage | None:
    if profile is None or profile.is_empty:
        return None
    lines = ["## Профиль пользователя"]
    if profile.title.strip():
        lines.append(f"Профиль: {profile.title.strip()}")
    identity = []
    if profile.name.strip():
        identity.append(f"Имя: {profile.name.strip()}")
    if profile.role.strip():
        identity.append(f"Роль: {profile.role.strip()}")
    if identity:
        lines.append("; ".join(identity))
    lines.append(
        f"Отвечай на языке: {LANGUAGE_LABELS.get(profile.language, profile.language)}"
    )
    lines.append(
        "Тон: "
        f"{TONE_LABELS.get(profile.tone, profile.tone)}; "
        f"Объём: {LENGTH_LABELS.get(profile.length, profile.length)}; "
        f"Формат: {STRUCTURE_LABELS.get(profile.structure, profile.structure)}"
    )
    if profile.constraints:
        lines.append("Ограничения:")
        lines.extend(f"- {item}" for item in profile.constraints)
    return ChatMessage(role="system", content="\n".join(lines))


def build_profile_trace(profile: UserProfile | None) -> dict | None:
    if build_profile_block(profile) is None:
        return None
    return {
        "title": profile.title,
        "name": profile.name,
        "role": profile.role,
        "language": profile.language,
        "tone": profile.tone,
        "length": profile.length,
        "structure": profile.structure,
        "constraints": list(profile.constraints),
    }


def normalize_profile_fields(fields: dict) -> dict:
    clean = dict(fields)
    if "tone" in clean and clean["tone"] not in PROFILE_TONES:
        raise ValueError("unknown tone")
    if "length" in clean and clean["length"] not in PROFILE_LENGTHS:
        raise ValueError("unknown length")
    if "structure" in clean and clean["structure"] not in PROFILE_STRUCTURES:
        raise ValueError("unknown structure")
    if "constraints" in clean:
        clean["constraints"] = [
            str(item).strip() for item in clean["constraints"] if str(item).strip()
        ]
    for key in ("title", "name", "role", "language"):
        if key in clean:
            clean[key] = str(clean[key]).strip()
    return clean
