from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HitSchema(BaseModel):
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


class AnswerSchema(BaseModel):
    mode: Literal["no_rag", "rag"]
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


class AnswerResponse(BaseModel):
    no_rag: AnswerSchema
    rag: AnswerSchema


class QuestionSchema(BaseModel):
    id: str
    question: str
    expectation: str
    sources: list[str]


class EvalItemSchema(BaseModel):
    question: str
    expectation: str
    sources: list[str]
    no_rag_answer: str
    no_rag_score: float
    rag_answer: str
    rag_score: float
    rag_sources: list[str]
    source_coverage: bool


class EvalReportSchema(BaseModel):
    items: list[EvalItemSchema]
    summary: dict
