import base64

from app.application.vision import encode_photo, photo_prompt


def test_encode_photo_roundtrip():
    data = b"\x00\x01\x02hello"
    assert base64.b64decode(encode_photo(data)) == data


def test_photo_prompt_default():
    assert photo_prompt(None) == "Опиши изображение"
    assert photo_prompt("") == "Опиши изображение"
    assert photo_prompt("что это?") == "что это?"
