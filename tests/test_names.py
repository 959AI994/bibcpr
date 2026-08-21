"""Person-name parser tests."""
from cpr.bibtex.names import parse_person, parse_person_list


def test_family_given_form():
    a = parse_person("Qian, Weikang")
    assert a.family == "Qian"
    assert a.given == ["Weikang"]


def test_given_family_form():
    a = parse_person("Weikang Qian")
    assert a.family == "Qian"
    assert a.given == ["Weikang"]


def test_hyphenated_given():
    a = parse_person("Pai-Shun Ting")
    assert a.family == "Ting"
    assert a.given == ["Pai-Shun"]


def test_particles_lastname_first():
    a = parse_person("van der Berg, Cornelis")
    assert a.family == "Berg"
    assert a.particles == ["van", "der"]
    assert a.given == ["Cornelis"]


def test_particles_firstname_first():
    a = parse_person("Cornelis van der Berg")
    assert a.family == "Berg"
    assert a.particles == ["van", "der"]
    assert a.given == ["Cornelis"]


def test_institutional_brace_group():
    a = parse_person("{OpenAI}")
    assert a.family == "OpenAI"
    assert a.given == []


def test_person_list_and_join():
    people = parse_person_list("Alice A and Bob B and Carol C")
    assert len(people) == 3
    assert [p.family for p in people] == ["A", "B", "C"]


def test_person_list_with_particles_and_commas():
    people = parse_person_list("van der Berg, Cornelis and Alice Doe")
    assert len(people) == 2
    assert people[0].family == "Berg"
    assert people[0].particles == ["van", "der"]
    assert people[1].family == "Doe"


def test_unicode_family_name():
    a = parse_person("Jürgen Müller")
    assert a.family == "Müller"
    assert a.given == ["Jürgen"]


def test_empty_input():
    a = parse_person("")
    assert a.family == ""
    assert a.given == []
