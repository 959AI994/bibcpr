"""Writer + citation-key preservation invariants."""
from pathlib import Path

from cpr.bibtex.parser import parse_bibtex_string, parse_bibtex_file
from cpr.bibtex.writer import write_entries


def test_writer_preserves_citation_keys():
    text = "@article{funky_Key.2023, author={A}, title={B}, year={2023}}"
    entries = parse_bibtex_string(text)
    out = write_entries(entries)
    assert "@article{funky_Key.2023," in out


def test_writer_round_trip_key_set_matches_input():
    text = """
    @article{a2020, author={X}, title={Y}, year={2020}}
    @inproceedings{b2021, author={Z}, title={W}, year={2021}}
    @misc{c2022, author={P}, title={Q}, year={2022}}
    """
    entries = parse_bibtex_string(text)
    out = write_entries(entries)
    parsed_back = parse_bibtex_string(out)
    assert sorted(e.key for e in entries) == sorted(e.key for e in parsed_back)


def test_writer_orders_fields_per_profile_order():
    text = "@article{k, doi={10.1/x}, year={2020}, author={A}, title={T}}"
    entries = parse_bibtex_string(text)
    order = ["author", "title", "year", "doi"]
    out = write_entries(entries, field_order=order)
    # find positions
    lines = out.splitlines()
    idxs = {}
    for i, ln in enumerate(lines):
        for field in order:
            if ln.strip().startswith(field + " ="):
                idxs.setdefault(field, i)
    assert idxs["author"] < idxs["title"] < idxs["year"] < idxs["doi"]


def test_writer_drops_empty_fields_when_configured():
    text = "@article{k, author={A}, title={T}, year={2020}, note={}}"
    entries = parse_bibtex_string(text)
    out = write_entries(entries, drop_if_empty=["note"])
    assert "note =" not in out


def test_all_golden_bibs_preserve_keys(bibs_dir: Path):
    """Citation-key preservation invariant across every golden case."""
    for bib_path in bibs_dir.glob("*.bib"):
        entries = parse_bibtex_file(bib_path)
        out = write_entries(entries)
        parsed_back = parse_bibtex_string(out)
        assert sorted(e.key for e in entries) == sorted(e.key for e in parsed_back), (
            f"key set changed for {bib_path.name}"
        )
