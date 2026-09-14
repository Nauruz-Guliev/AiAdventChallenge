import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.models import (
    AuthenticationGatewayError,
    ChatNotFound,
    ChatPersistenceError,
    GatewayTimeoutError,
    InvalidUserMessage,
    LLMGatewayError,
    RateLimitGatewayError,
)
from app.presentation.routes import router


logger = logging.getLogger(__name__)
app = FastAPI(title="Day 8 Token Counting")
app.include_router(router)


@app.exception_handler(InvalidUserMessage)
async def invalid_message_handler(request: Request, error: InvalidUserMessage):
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(ChatNotFound)
async def chat_not_found_handler(request: Request, error: ChatNotFound):
    return JSONResponse(status_code=404, content={"detail": "Чат не найден."})


@app.exception_handler(ChatPersistenceError)
async def chat_persistence_error_handler(request: Request, error: ChatPersistenceError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Не удалось загрузить или сохранить историю чата."},
    )


@app.exception_handler(AuthenticationGatewayError)
async def authentication_error_handler(request: Request, error: AuthenticationGatewayError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Провайдер отклонил API-ключ. Проверьте .env."},
    )


@app.exception_handler(RateLimitGatewayError)
async def rate_limit_error_handler(request: Request, error: RateLimitGatewayError):
    return JSONResponse(
        status_code=429,
        content={"detail": "Провайдер временно ограничил запросы. Повторите позже."},
    )


@app.exception_handler(GatewayTimeoutError)
async def timeout_error_handler(request: Request, error: GatewayTimeoutError):
    return JSONResponse(
        status_code=504,
        content={"detail": "Провайдер не ответил вовремя. Повторите запуск."},
    )


@app.exception_handler(LLMGatewayError)
async def gateway_error_handler(request: Request, error: LLMGatewayError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Не удалось получить ответ от провайдера."},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception):
    logger.exception("Unexpected request error", exc_info=error)
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера."},
    )
