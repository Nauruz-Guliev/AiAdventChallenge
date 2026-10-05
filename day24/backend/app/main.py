from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.models import IndexNotFound, InvalidQuestion, LLMGatewayError
from app.presentation.routes import router

app = FastAPI(title="Day 24 Citations and Anti-Hallucination")
app.include_router(router)


@app.exception_handler(InvalidQuestion)
async def invalid_question_handler(request: Request, error: InvalidQuestion):
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.exception_handler(IndexNotFound)
async def index_not_found_handler(request: Request, error: IndexNotFound):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(LLMGatewayError)
async def gateway_error_handler(request: Request, error: LLMGatewayError):
    return JSONResponse(status_code=502, content={"detail": "Не удалось получить ответ от LLM."})
