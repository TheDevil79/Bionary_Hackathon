import pytest
from app.ingestion.chunker import chunk_text, split_into_sentences


def test_split_into_sentences():
    text = "First sentence here. Second sentence starts now! Is this the third? Yes it is."
    sentences = split_into_sentences(text)
    assert len(sentences) == 4
    assert sentences[0] == "First sentence here."
    assert sentences[1] == "Second sentence starts now!"


def test_chunk_short_text():
    text = "A very short claim."
    chunks = chunk_text(text, source_id="src_1", chunk_size=200, chunk_overlap=50)
    assert len(chunks) == 1
    assert chunks[0].text == "A very short claim."
    assert chunks[0].chunk_index == 0


def test_chunk_large_text_overlap():
    paragraph = (
        "Meteorological stations recorded heavy rainfall across coastal districts on Thursday afternoon. "
        "The continuous downpour caused localized flash floods in several low-lying streets and subway underpasses. "
        "Emergency rescue teams and municipal crews were deployed with high-capacity dewatering pumps. "
        "Traffic police advised commuters to seek alternative arterial routes until floodwaters receded."
    )
    chunks = chunk_text(paragraph, source_id="src_flood", chunk_size=150, chunk_overlap=50)
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.source_id == "src_flood"
        assert c.chunk_index == i
        assert len(c.text) > 0
