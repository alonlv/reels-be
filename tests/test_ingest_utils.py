from app.ingest.dedupe import dedup_hash
from app.ingest.classify import classify_url


def test_dedup_hash_stable_and_case_insensitive_title():
    a = dedup_hash("https://e.com/x", "Hello World")
    b = dedup_hash("https://e.com/x", "hello world")
    assert a == b
    assert len(a) == 64


def test_classify_url():
    assert classify_url("https://www.youtube.com/watch?v=abc") == "youtube"
    assert classify_url("https://youtu.be/abc") == "youtube"
    assert classify_url("https://twitter.com/foo/status/1") == "x"
    assert classify_url("https://x.com/foo/status/1") == "x"
    assert classify_url("https://www.reddit.com/r/ml/comments/1/x") == "reddit"
    assert classify_url("https://example.com/blog/post") == "article"
