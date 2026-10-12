from __future__ import annotations

from app.domain.models import OptimizationProfile, Quant

BASELINE_OPTIONS = {"num_ctx": 8192}
TUNED_OPTIONS = {
    "num_ctx": 4096,
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512,
    "repeat_penalty": 1.1,
}

PROFILE_ORDER = ("baseline", "params", "optimized")
PROFILES: dict[str, OptimizationProfile] = {
    "baseline": OptimizationProfile("baseline", "Базовая (день 28)", dict(BASELINE_OPTIONS), "baseline"),
    "params": OptimizationProfile("params", "+Параметры", dict(TUNED_OPTIONS), "baseline"),
    "optimized": OptimizationProfile("optimized", "+Промпт", dict(TUNED_OPTIONS), "optimized"),
}

QUANT_ORDER = ("q4", "q8")
QUANTS: dict[str, Quant] = {
    "q4": Quant("q4", "gemma4:12b", "Q4_K_M", 8.0),
    "q8": Quant("q8", "gemma4:12b-it-q8_0", "Q8_0", 13.0),
}


def get_profile(name: str) -> OptimizationProfile:
    return PROFILES.get(name, PROFILES["optimized"])


def get_quant(name: str) -> Quant:
    return QUANTS.get(name, QUANTS["q4"])


def next_profile(name: str) -> str:
    order = PROFILE_ORDER
    return order[(order.index(name) + 1) % len(order)] if name in order else order[0]


def next_quant(name: str) -> str:
    order = QUANT_ORDER
    return order[(order.index(name) + 1) % len(order)] if name in order else order[0]
