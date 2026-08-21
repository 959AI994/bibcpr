"""Parser tests — offline, no network."""
from cpr.bibtex.parser import parse_bibtex_string
from cpr.bibtex.identity import extract_identity, normalize_title


def test_parser_reads_basic_entry():
    text = """
    @article{smith2024,
      author = {John Smith and Jane Doe},
      title = {Some Title},
      journal = {Nature},
      year = {2024},
      pages = {1--10},
      doi = {10.1234/abc}
    }
    """
    entries = parse_bibtex_string(text)
    assert len(entries) == 1
    e = entries[0]
    assert e.key == "smith2024"
    assert e.entry_type == "article"
    assert e.title == "Some Title"
    assert e.year == 2024
    assert len(e.authors) == 2
    assert e.authors[0].family == "Smith"
    assert e.authors[0].given == ["John"]
    assert e.doi == "10.1234/abc"


def test_parser_preserves_citation_key():
    text = "@article{my-Weird_Key.2023, author = {A}, title = {B}, year = {2023}}"
    entries = parse_bibtex_string(text)
    assert entries[0].key == "my-Weird_Key.2023"


def test_parser_extracts_arxiv_id_from_eprint():
    text = """
    @article{arxpaper,
      author = {A},
      title = {B},
      eprint = {2301.12345},
      archivePrefix = {arXiv},
      year = {2023}
    }
    """
    entry = parse_bibtex_string(text)[0]
    identity = extract_identity(entry)
    assert identity.arxiv_id == "2301.12345"


def test_normalize_title_strips_latex_and_lowercases():
    assert normalize_title("Attention Is All You Need") == "attention is all you need"
    assert normalize_title("On $O(n^2)$ Bounds") == "on o n 2 bounds"
    assert normalize_title(r"\emph{Fancy} Title.") == "fancy title"


def test_parser_handles_empty_input():
    assert parse_bibtex_string("") == []
    assert parse_bibtex_string("% just a comment\n") == []


def test_parser_multiple_entries():
    text = """
    @article{a, author={X}, title={Y}, year={2020}}
    @inproceedings{b, author={Z}, title={W}, year={2021}}
    """
    entries = parse_bibtex_string(text)
    assert len(entries) == 2
    assert [e.key for e in entries] == ["a", "b"]
    assert entries[1].entry_type == "inproceedings"
