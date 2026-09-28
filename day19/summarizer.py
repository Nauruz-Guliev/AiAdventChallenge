from __future__ import annotations

import re

STOP_WORDS = {
    "это", "как", "что", "для", "его", "ее", "её", "их", "или", "они", "она", "он",
    "при", "так", "то", "на", "по", "из", "от", "до", "в", "во", "с", "со", "не",
    "но", "а", "и", "к", "о", "об", "у", "за", "над", "под", "мы", "вы", "ты", "я",
    "быть", "есть", "был", "была", "были", "будет", "могут", "может", "также",
    "который", "которая", "которые", "которое", "этого", "этой", "этом", "эту",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip())]
    return [p for p in parts if p]


def _words(sentence: str) -> list[str]:
    return re.findall(r"[а-яёa-z]+", sentence.lower())


def _score(text_sentences: list[str], freq: dict[str, int]) -> list[float]:
    scores = []
    for sentence in text_sentences:
        words = _words(sentence)
        if not words:
            scores.append(0.0)
            continue
        total = sum(freq.get(w, 0) for w in words)
        scores.append(total / len(words))
    return scores


def summarize(text: str, sentences: int = 3) -> dict:
    sents = _sentences(text)
    if not sents:
        return {"summary": "", "original_chars": len(text), "summary_chars": 0, "sentence_count": 0}

    freq: dict[str, int] = {}
    for sentence in sents:
        for word in _words(sentence):
            if len(word) >= 3 and word not in STOP_WORDS:
                freq[word] = freq.get(word, 0) + 1

    scores = _score(sents, freq)
    ranked = sorted(range(len(sents)), key=lambda i: scores[i], reverse=True)
    n = max(1, min(sentences, len(sents)))
    chosen = sorted(ranked[:n])
    summary = " ".join(sents[i] for i in chosen)
    return {
        "summary": summary,
        "original_chars": len(text),
        "summary_chars": len(summary),
        "sentence_count": n,
    }
