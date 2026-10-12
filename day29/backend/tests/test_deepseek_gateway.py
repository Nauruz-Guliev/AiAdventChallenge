import pytest

from app.domain.models import ChatMessage, Role
from app.infrastructure.deepseek_gateway import DeepSeekGateway


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content=None, error=None):
        self._content, self._error = content, error

    async def create(self, **kwargs):
        if self._error:
            raise self._error
        return _Resp(self._content)


class _Client:
    def __init__(self, completions):
        self.chat = type("C", (), {"completions": completions})()


@pytest.mark.asyncio
async def test_complete_ok():
    gw = DeepSeekGateway("k", "http://x", "deepseek-chat",
                         client=_Client(_Completions(content="  hi  ")))
    out = await gw.complete([ChatMessage(Role.USER, "q")])
    assert out.text == "hi"


@pytest.mark.asyncio
async def test_complete_empty_raises():
    from app.domain.models import CloudUnavailable

    gw = DeepSeekGateway("k", "http://x", "m", client=_Client(_Completions(content="")))
    with pytest.raises(CloudUnavailable):
        await gw.complete([ChatMessage(Role.USER, "q")])
