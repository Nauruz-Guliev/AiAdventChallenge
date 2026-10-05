from chunking import count_tokens, chunk_fixed


TEXT = " ".join(f"w{i}" for i in range(1000))


def test_fixed_no_empty_and_unique_ids():
    chunks = chunk_fixed(TEXT, chunk_size=100, overlap=10, source="doc.md", title="Doc")
    assert chunks
    assert all(c.text.strip() for c in chunks)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.chunk_id.startswith("doc.md:fixed:") for c in chunks)


def test_fixed_overlap():
    chunks = chunk_fixed(TEXT, chunk_size=10, overlap=2)
    first = chunks[0].text.split()
    second = chunks[1].text.split()
    assert first[-2:] == second[:2]


def test_fixed_metadata():
    chunks = chunk_fixed("a b c d e", chunk_size=2, overlap=0, source="s.md", title="T")
    c = chunks[0]
    assert c.source == "s.md" and c.title == "T"
    assert c.strategy == "fixed" and c.section == "fixed"
    assert c.token_count == 2 and c.char_offset == 0


def test_count_tokens_fallback():
    assert count_tokens("one two three") == 3
    assert count_tokens("one two three", tokenizer=lambda t: list(t.split())) == 3


def test_fixed_empty_text():
    assert chunk_fixed("") == []
