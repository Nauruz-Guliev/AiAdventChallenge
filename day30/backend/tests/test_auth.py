import pytest

from app.domain.models import Unauthorized
from app.presentation.auth import authorize, extract_key


def test_extract_key_prefers_header():
    assert extract_key("abc", None) == "abc"
    assert extract_key(None, "Bearer xyz") == "xyz"
    assert extract_key(None, "bearer xyz") == "xyz"


def test_extract_key_none_when_absent_or_malformed():
    assert extract_key(None, None) is None
    assert extract_key(None, "Token abc") is None
    assert extract_key(None, "Bearer") is None


def test_authorize_anonymous_when_no_keys_configured():
    assert authorize(None, set(), require=False) == "anonymous"


def test_authorize_requires_key_when_mandatory():
    with pytest.raises(Unauthorized):
        authorize(None, set(), require=True)


def test_authorize_rejects_wrong_key():
    with pytest.raises(Unauthorized):
        authorize("nope", {"good"}, require=False)


def test_authorize_accepts_configured_key():
    identity = authorize("good", {"good"}, require=False)
    assert identity.startswith("key:")
