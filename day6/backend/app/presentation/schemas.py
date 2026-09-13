from pydantic import BaseModel, Field, field_validator

from app.domain.models import StageStatus


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class StageResponse(BaseModel):
    name: str
    status: StageStatus


class ChatResponse(BaseModel):
    answer: str
    model: str
    duration_ms: int
    stages: list[StageResponse]
