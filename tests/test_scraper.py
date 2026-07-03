from app.ingest.scraper import parse_metadata


def test_parse_og_tags():
    html = """
    <html><head>
      <meta property="og:title" content="Cool AI Thing">
      <meta property="og:image" content="https://img.example/x.png">
      <meta property="og:description" content="A short summary.">
    </head><body></body></html>
    """
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["title"] == "Cool AI Thing"
    assert meta["image_url"] == "https://img.example/x.png"
    assert meta["summary"] == "A short summary."


def test_parse_falls_back_to_title_tag():
    html = "<html><head><title>Plain Title</title></head><body></body></html>"
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["title"] == "Plain Title"
    assert meta["image_url"] is None
