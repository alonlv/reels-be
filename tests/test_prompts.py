from app.llm.prompts import coerce_explanation, parse_explanation


def test_parse_plain_json():
    out = parse_explanation('{"short": "a blurb", "long": "the deep dive"}')
    assert out == {"short": "a blurb", "long": "the deep dive"}


def test_parse_json_in_code_fence():
    raw = '```json\n{"short": "hi", "long": "there"}\n```'
    assert parse_explanation(raw) == {"short": "hi", "long": "there"}


def test_parse_json_with_surrounding_prose():
    raw = 'Sure! Here you go:\n{"short": "s", "long": "l"}\nHope that helps.'
    assert parse_explanation(raw) == {"short": "s", "long": "l"}


def test_parse_returns_none_for_garbage():
    assert parse_explanation("not json at all") is None
    assert parse_explanation("") is None


def test_coerce_falls_back_to_short_only():
    out = coerce_explanation("just a plain sentence")
    assert out == {"short": "just a plain sentence", "long": None}


def test_coerce_uses_parsed_when_available():
    out = coerce_explanation('{"short": "x", "long": "y"}')
    assert out == {"short": "x", "long": "y"}
