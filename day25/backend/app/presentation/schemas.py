from pydantic import BaseModel, Field, field_validator


class SessionCreateSchema(BaseModel):
    goal: str = ""

    @field_validator("goal")
    @classmethod
    def clean(cls, value: str) -> str:
        return (value or "").strip()


class MessageRequestSchema(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class HitSchema(BaseModel):
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


class CitationSchema(BaseModel):
    ref: int
    chunk_id: str
    source: str
    section: str
    quote: str
    grounded: bool


class TaskMemorySchema(BaseModel):
    goal: str
    clarifications: list[str]
    constraints: list[str]
    terms: list[str]


class MessageSchema(BaseModel):
    role: str
    text: str
    at: str
    sources: list[HitSchema]
    citations: list[CitationSchema]


class SessionSchema(BaseModel):
    id: str
    created_at: str
    memory: TaskMemorySchema
    messages: list[MessageSchema]


class SessionSummarySchema(BaseModel):
    id: str
    created_at: str
    goal: str
    n_messages: int


class TurnResponseSchema(BaseModel):
    reply: str
    sources: list[HitSchema]
    citations: list[CitationSchema]
    memory: TaskMemorySchema
    answerable: bool
    relevance: float | None


class ScenarioReportSchema(BaseModel):
    name: str
    turns: int
    all_with_sources: bool
    goal_kept: bool
    memory_grown: bool
    passed: bool
    final_memory: dict
