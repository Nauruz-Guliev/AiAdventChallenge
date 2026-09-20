import hashlib
import urllib.request

from app.domain.models import ChatMessage
from app.infrastructure.token_counter import (
    PER_MESSAGE_OVERHEAD_TOKENS,
    TiktokenCounter,
    ensure_encoding_cached,
)


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_ensure_encoding_cached_downloads_and_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    calls = []

    def fake_urlopen(url, context=None, timeout=None):
        calls.append((url, timeout))
        return FakeResponse(b"fake bpe data")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    path = ensure_encoding_cached("cl100k_base")

    assert calls[0][0] == (
        "https://openaipublic.blob.core.windows.net/"
        "encodings/cl100k_base.tiktoken"
    )
    assert calls[0][1] == 60
    expected_name = hashlib.sha1(calls[0][0].encode("utf-8")).hexdigest()
    assert path == tmp_path / expected_name
    assert path.read_bytes() == b"fake bpe data"


def test_ensure_encoding_cached_skips_download_when_file_exists(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    blob = (
        "https://openaipublic.blob.core.windows.net/"
        "encodings/cl100k_base.tiktoken"
    )
    expected = tmp_path / hashlib.sha1(blob.encode("utf-8")).hexdigest()
    expected.write_bytes(b"already here")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("download must not happen when cache exists")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    assert ensure_encoding_cached("cl100k_base") == expected


def test_count_text_returns_zero_for_empty_string():
    assert TiktokenCounter().count_text("") == 0


def test_count_text_counts_known_english_phrase():
    assert TiktokenCounter().count_text("hello world") == 2


def test_count_text_counts_russian_text_more_than_words():
    assert TiktokenCounter().count_text("сколько стоит контекст") > 4


def test_count_messages_adds_per_message_overhead():
    counter = TiktokenCounter()
    messages = [
        ChatMessage(role="system", content="hello world"),
        ChatMessage(role="user", content="hello world"),
    ]

    assert counter.count_messages(messages) == 2 * (
        2 + PER_MESSAGE_OVERHEAD_TOKENS
    )
