from keys import format_key, to_camelot, to_open_key


def test_to_camelot_minor_and_major():
    assert to_camelot("A Minor") == "8A"
    assert to_camelot("C Major") == "8B"
    assert to_camelot("E Minor") == "9A"


def test_to_camelot_accidentals_and_short_forms():
    assert to_camelot("F# Minor") == "11A"
    assert to_camelot("Db Major") == "3B"   # flat normalised to C#
    assert to_camelot("A min") == "8A"      # short mode token


def test_to_camelot_unknown_returns_none():
    assert to_camelot("Not A Key") is None
    assert to_camelot("") is None
    assert to_camelot(None) is None


def test_to_open_key():
    assert to_open_key("8A") == "1m"   # A minor
    assert to_open_key("8B") == "1d"   # C major
    assert to_open_key("9A") == "2m"
    assert to_open_key(None) is None


def test_format_key_derives_from_name():
    assert format_key({"name": "A Minor"}) == "A Minor (Camelot 8A, Open Key 1m)"


def test_format_key_prefers_native_camelot_fields():
    obj = {"name": "C Major", "camelot_number": 8, "camelot_letter": "B"}
    assert format_key(obj) == "C Major (Camelot 8B, Open Key 1d)"


def test_format_key_falls_back_to_plain_name():
    assert format_key({"name": "Weird"}) == "Weird"
    assert format_key(None) is None
