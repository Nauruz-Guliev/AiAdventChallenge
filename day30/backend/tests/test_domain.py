from app.domain.models import (
    ContextBudgetExceeded,
    InvalidRequest,
    Overloaded,
    RateLimited,
    ServiceError,
    Unauthorized,
    Usage,
)


def test_usage_of_sums_total():
    u = Usage.of(10, 5)
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (10, 5, 15)


def test_errors_carry_status_and_code():
    assert isinstance(InvalidRequest("x"), ServiceError)
    assert Unauthorized("x").status == 401
    assert ContextBudgetExceeded("x").status == 400
    assert ContextBudgetExceeded("x").code == "context_length_exceeded"
    assert RateLimited("x", retry_after=3).retry_after == 3
    assert RateLimited("x", retry_after=3).status == 429
    assert Overloaded("x", retry_after=2).status == 503
