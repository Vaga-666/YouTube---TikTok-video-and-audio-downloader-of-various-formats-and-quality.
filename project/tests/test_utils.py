from app.utils.paths import safe_filename
from app.utils import ratelimit


def test_safe_filename_allows_basic_chars():
    assert safe_filename("Видео тест.mp4") == "Видео тест.mp4"
    sanitized = safe_filename("bad/../name")
    assert "/" not in sanitized
    assert ".." not in sanitized
    assert safe_filename("", fallback="default") == "default"


def test_rate_limit_allows_limited_calls():
    ratelimit.reset()
    ip = "127.0.0.1"
    for _ in range(ratelimit.LIMIT):
        assert ratelimit.allow(ip)
    assert not ratelimit.allow(ip)
