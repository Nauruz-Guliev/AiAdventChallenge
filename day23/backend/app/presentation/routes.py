import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator
from app.domain.models import Answer, EvalReport, Question
from app.infrastructure.settings import Settings
from app.presentation.dependencies import (
    get_agent,
    get_evaluator,
    get_questions,
    get_settings,
)
from app.presentation.schemas import (
    AnswerRequest,
    AnswerResponse,
    AnswerSchema,
    EvalReportSchema,
    HitSchema,
    QuestionSchema,
)

router = APIRouter()
_post = router.post
_get = router.get


def _answer_schema(answer: Answer) -> AnswerSchema:
    return AnswerSchema(
        mode=answer.mode,
        text=answer.text,
        sources=[
            HitSchema(
                chunk_id=h.chunk_id,
                source=h.source,
                title=h.title,
                section=h.section,
                score=h.score,
                text=h.text,
            )
            for h in answer.sources
        ],
    )


def _item_dict(item) -> dict:
    return {
        "question": item.question,
        "expectation": item.expectation,
        "sources": item.sources,
        "no_rag_answer": item.no_rag_answer,
        "no_rag_score": item.no_rag_score,
        "rag_answer": item.rag_answer,
        "rag_score": item.rag_score,
        "rag_sources": item.rag_sources,
        "source_coverage": item.source_coverage,
    }


def _report_dict(report: EvalReport) -> dict:
    return {
        "items": [_item_dict(item) for item in report.items],
        "summary": report.summary,
    }


@_post("/api/answer", response_model=AnswerResponse)
async def answer(
    request: AnswerRequest,
    agent: Annotated[RAGAgent, Depends(get_agent)],
) -> AnswerResponse:
    no_rag = await agent.answer(request.question, mode="no_rag")
    rag = await agent.answer(request.question, mode="rag")
    return AnswerResponse(no_rag=_answer_schema(no_rag), rag=_answer_schema(rag))


@_get("/api/questions", response_model=list[QuestionSchema])
async def list_questions(
    questions: Annotated[list[Question], Depends(get_questions)],
) -> list[QuestionSchema]:
    return [
        QuestionSchema(
            id=q.id, question=q.question, expectation=q.expectation, sources=list(q.sources)
        )
        for q in questions
    ]


@_post("/api/eval", response_model=EvalReportSchema)
async def run_eval(
    evaluator: Annotated[Evaluator, Depends(get_evaluator)],
    questions: Annotated[list[Question], Depends(get_questions)],
    settings: Annotated[Settings, Depends(get_settings)],
    force: bool = False,
) -> EvalReportSchema:
    report_path = Path(settings.eval_report_path)
    if report_path.exists() and not force:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        return EvalReportSchema(**data)
    report = await evaluator.evaluate(questions)
    payload = _report_dict(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return EvalReportSchema(**payload)
