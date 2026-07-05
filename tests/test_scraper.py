from app.ingest.scraper import clean_text, parse_metadata


def test_clean_text_strips_tags_and_entities():
    raw = ('<blockquote>&quot;Language back as thought&quot; &#x2013;Winograd'
           '</blockquote><p>The recent successes of generative AI.</p>')
    assert clean_text(raw) == (
        '"Language back as thought" –Winograd '
        "The recent successes of generative AI."
    )


def test_clean_text_handles_escaped_markup_and_empty():
    assert clean_text("&lt;p&gt;hi &amp; bye&lt;/p&gt;") == "hi & bye"
    assert clean_text("") is None
    assert clean_text(None) is None


def test_parse_metadata_cleans_summary_html():
    html = ('<html><head>'
            '<meta property="og:description" content="A &amp; B &#x2013; C">'
            "</head><body></body></html>")
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["summary"] == "A & B – C"


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


def test_image_falls_back_to_twitter_then_inline():
    html = """
    <html><head><meta name="twitter:image" content="https://img.example/t.png">
    </head><body><img src="/first.jpg"></body></html>
    """
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["image_url"] == "https://img.example/t.png"


def test_image_resolves_relative_inline_img():
    html = "<html><head></head><body><img src='/media/hero.jpg'></body></html>"
    meta = parse_metadata(html, "https://example.com/post/1")
    assert meta["image_url"] == "https://example.com/media/hero.jpg"


def test_extracts_body_text_without_scripts():
    html = """
    <html><head><title>T</title></head>
    <body><script>var x = 1;</script><p>Hello world.</p>
    <style>.a{}</style><p>Second line.</p></body></html>
    """
    meta = parse_metadata(html, "https://example.com/a")
    assert meta["text"] == "Hello world. Second line."


def test_text_is_none_for_empty_body():
    meta = parse_metadata("<html><body></body></html>", "https://example.com/a")
    assert meta["text"] is None
