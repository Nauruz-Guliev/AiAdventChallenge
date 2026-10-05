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


from chunking import chunk_structure


MD = """# Title

Intro text here.

## Section A

Alpha beta gamma delta epsilon zeta eta theta iota kappa.

## Section B

One two three four five six seven eight nine ten.

# Another

Some more text for the second top-level section.
"""


def test_structure_splits_by_headings():
    chunks = chunk_structure(MD, source="d.md", title="Title", min_tokens=1)
    assert len(chunks) >= 3
    sections = [c.section for c in chunks]
    assert any("Section A" in s for s in sections)
    assert any("Another" in s for s in sections)


def test_structure_section_path_and_ids():
    chunks = chunk_structure(MD, source="d.md", title="Title", min_tokens=1)
    assert all(c.strategy == "structure" for c in chunks)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("d.md:struct:") for i in ids)


def test_structure_merges_small_sections():
    small = "\n".join(f"## H{i}\nword{i}" for i in range(5))
    merged = chunk_structure(small, source="s.md", min_tokens=100)
    assert 1 <= len(merged) < 5


def test_structure_empty():
    assert chunk_structure("", source="e.md") == []


class _CharTokenizer:
    """Каждый символ = токен. Проверяем токенизаторный путь (spans)."""

    def tokenize(self, text):
        return list(text)

    def spans(self, text):
        return [(i, i + 1) for i in range(len(text))]


def test_count_tokens_with_tokenizer_object():
    assert count_tokens("abcd", tokenizer=_CharTokenizer()) == 4


def test_fixed_uses_tokenizer_spans():
    chunks = chunk_fixed(
        "abcdefghij", chunk_size=4, overlap=0, tokenizer=_CharTokenizer(), source="x"
    )
    assert [c.text for c in chunks] == ["abcd", "efgh", "ij"]
    assert chunks[0].token_count == 4


def test_structure_splits_oversized_section():
    md = "## Big\n" + "word " * 20
    chunks = chunk_structure(md, source="s.md", max_tokens=5, min_tokens=1)
    assert len(chunks) > 1
    assert all(c.token_count <= 5 for c in chunks)
