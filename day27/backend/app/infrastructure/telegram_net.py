from __future__ import annotations

import socket

_orig_getaddrinfo = None
_override_ip: str | None = None


def force_telegram_api_ip(ip: str) -> None:
    """Резолвит api.telegram.org в указанный IP.

    Нужно в сетях, где DNS выдаёт заблокированный IP Telegram, а другой IP
    того же Bot API доступен. SNI и сертификат остаются для api.telegram.org,
    меняется только адрес, к которому идёт соединение.
    """
    global _orig_getaddrinfo, _override_ip
    if not ip:
        return
    if _orig_getaddrinfo is None:
        _orig_getaddrinfo = socket.getaddrinfo
    _override_ip = ip
    original = _orig_getaddrinfo

    def patched(host, port, *args, **kwargs):
        if host == "api.telegram.org" and _override_ip:
            host = _override_ip
        return original(host, port, *args, **kwargs)

    socket.getaddrinfo = patched


def restore() -> None:
    global _orig_getaddrinfo, _override_ip
    if _orig_getaddrinfo is not None:
        socket.getaddrinfo = _orig_getaddrinfo
    _orig_getaddrinfo = None
    _override_ip = None
