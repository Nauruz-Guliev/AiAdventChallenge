from pydantic import BaseModel, Field, field_validator


class HitSchema(BaseModel):
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


class AnswerSchema(BaseModel):
    mode: str
    text: str
    sources: list[HitSchema]


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value


class ModesResponse(BaseModel):
    modes: dict[str, AnswerSchema]


class QuestionSchema(BaseModel):
    id: str
    question: str
    expectation: str
    sources: list[str]


class EvalItemSchema(BaseModel):
    question: str
    expectation: str
    sources: list[str]
    mode_answers: dict[str, str]
    mode_scores: dict[str, float]
    mode_sources: dict[str, list[str]]
    source_coverage: dict[str, bool]


class EvalReportSchema(BaseModel):
    items: list[EvalItemSchema]
    summary: dict
