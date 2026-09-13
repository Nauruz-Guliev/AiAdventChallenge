from app.domain.models import AgentResult, AgentStage, LLMResponse


def test_result_contains_answer_model_duration_and_stages():
    result = AgentResult(
        answer="test answer",
        model="deepseek-chat",
        duration_ms=12,
        stages=[AgentStage(name="Agent", status="completed")],
    )

    assert result.answer == "test answer"
    assert result.model == "deepseek-chat"
    assert result.stages[0].status == "completed"


def test_llm_response_contains_text_and_model():
    response = LLMResponse(text="hello", model="deepseek-chat")

    assert response.text == "hello"
