from app.ingest.categorize import CATEGORIES, categorize, normalize_category


def test_categorize_by_keyword():
    assert categorize("Startup raises $40M Series B") == "business"
    assert categorize("New paper sets SOTA on the benchmark") == "research"
    assert categorize("EU passes sweeping AI regulation") == "policy"
    assert categorize("We open-source the model weights on GitHub") == "open-source"
    assert categorize("How to build a RAG pipeline: a guide") == "tutorial"
    assert categorize("Introducing our new app") == "product"


def test_categorize_defaults_to_other():
    assert categorize("A quiet afternoon", "nothing notable") == "other"


def test_categorize_always_valid():
    assert categorize(None) in CATEGORIES


def test_normalize_category():
    assert normalize_category("Research") == "research"
    assert normalize_category("open_source") == "open-source"
    assert normalize_category("open source") == "open-source"
    assert normalize_category("banana") is None
    assert normalize_category(None) is None
