from dataclasses import dataclass

INVARIANT_CATEGORIES = ("architecture", "decision", "stack", "business")

INVARIANT_CATEGORY_LABELS = {
    "architecture": "архитектура",
    "decision": "технические решения",
    "stack": "ограничения стека",
    "business": "бизнес-правила",
}


class InvariantNotFound(RuntimeError):
    pass


@dataclass
class Invariant:
    id: str
    text: str
    category: str = "decision"

    @property
    def category_label(self) -> str:
        return INVARIANT_CATEGORY_LABELS.get(self.category, self.category)
