import socket

import app.infrastructure.telegram_net as tn
from app.infrastructure.telegram_net import force_telegram_api_ip, restore


def test_override_maps_telegram_host():
    restore()
    try:
        force_telegram_api_ip("203.0.113.7")
        addrs = {i[4][0] for i in socket.getaddrinfo("api.telegram.org", 443)}
        assert "203.0.113.7" in addrs
    finally:
        restore()


def test_other_hosts_unaffected():
    restore()
    try:
        force_telegram_api_ip("203.0.113.7")
        infos = socket.getaddrinfo("localhost", 80)
        assert infos
    finally:
        restore()


def test_empty_is_noop():
    restore()
    force_telegram_api_ip("")
    assert tn._orig_getaddrinfo is None
    restore()
