import pytest

from app.services.chunking import DocumentParseError, chunk_text, parse_requirement_file


def test_chunk_text_splits_on_size_with_overlap():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("   ", chunk_size=100, chunk_overlap=10) == []


def test_chunk_text_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text("hello world", chunk_size=10, chunk_overlap=10)


def test_parse_requirement_file_txt():
    content = b"Mobile OTP must be verified before loan submission. " * 20
    candidates = parse_requirement_file("rules.txt", content, chunk_size=100, chunk_overlap=20)
    assert len(candidates) > 0
    assert all(c.metadata["filename"] == "rules.txt" for c in candidates)
    assert all(c.metadata["page_number"] is None for c in candidates)


def test_parse_requirement_file_md():
    content = b"# Heading\n\nSome markdown requirement text goes here. " * 10
    candidates = parse_requirement_file("spec.md", content, chunk_size=100, chunk_overlap=20)
    assert len(candidates) > 0


def test_parse_requirement_file_bad_encoding_raises():
    with pytest.raises(DocumentParseError):
        parse_requirement_file("bad.txt", b"\xff\xfe\x00broken", chunk_size=100, chunk_overlap=20)


def test_parse_requirement_file_corrupt_pdf_raises():
    with pytest.raises(DocumentParseError):
        parse_requirement_file("fake.pdf", b"not a real pdf", chunk_size=100, chunk_overlap=20)


def test_parse_requirement_file_unsupported_extension_raises():
    with pytest.raises(DocumentParseError):
        parse_requirement_file("data.docx", b"whatever", chunk_size=100, chunk_overlap=20)
