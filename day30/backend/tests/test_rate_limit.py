from app.application.rate_limit import RateLimiter, TokenBucket


def test_bucket_allows_up_to_capacity_then_blocks():
    bucket = TokenBucket(capacity=2, refill_per_sec=1.0, tokens=2, updated_at=0.0)
    assert bucket.allow(0.0)[0] is True
    assert bucket.allow(0.0)[0] is True
    allowed, retry = bucket.allow(0.0)
    assert allowed is False and retry > 0


def test_bucket_refills_over_time():
    bucket = TokenBucket(capacity=1, refill_per_sec=1.0, tokens=0, updated_at=0.0)
    assert bucket.allow(0.5)[0] is False
    assert bucket.allow(1.0)[0] is True


def test_limiter_is_per_identity():
    limiter = RateLimiter(per_minute=60, burst=1)
    assert limiter.check("a", 0.0)[0] is True
    assert limiter.check("b", 0.0)[0] is True
    allowed, retry = limiter.check("a", 0.0)
    assert allowed is False
    assert retry >= 1


def test_limiter_eventually_recovers():
    limiter = RateLimiter(per_minute=60, burst=1)
    limiter.check("a", 0.0)
    assert limiter.check("a", 2.0)[0] is True
