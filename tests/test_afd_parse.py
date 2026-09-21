from jagged.substrates.afd_parse import Close, parse_close, strip_invisibles

KEEP = ("{{Afd top/old}}  The result was '''keep'''‎__EXPECTED_UNCONNECTED_PAGE__. "
        "<small>[[Wikipedia:NACD|(non-admin closure)]]</small> [[User:The Herald|The Herald]] "
        "02:33, 11 March 2024 (UTC)\n===[[:Kieran Woolley]]===")

DELETE = ("{{Afd top/old}}  The result was '''delete'''‎__EXPECTED_UNCONNECTED_PAGE__. "
          "The article can be restored if an editor comes forward with an argument that the "
          "subject meets the [[WP:GNG|GNG]]. [[User:Arbitrarily0|Arbitrarily0]]")

SOFT = ("{{Afd top/old}}  The result was '''soft delete'''‎__EXPECTED_UNCONNECTED_PAGE__. "
        "Based on [[WP:NOQUORUM|minimal participation]], this uncontroversial nomination is "
        "treated as an expired [[WP:PROD|PROD]].")

OPEN = "===[[:Some Article]]===\n:{{la|1=Some Article}}\nNominating, fails [[WP:GNG]]. ~~~~"


def test_strip_invisibles_removes_bidi_marks():
    assert strip_invisibles("keep‎‏​") == "keep"


def test_parses_keep_and_flags_non_admin_closure():
    c = parse_close(KEEP)
    assert c.result == "keep"
    assert c.normalized == "keep"
    assert c.non_admin is True


def test_parses_delete_and_captures_rationale():
    c = parse_close(DELETE)
    assert c.normalized == "delete"
    assert c.non_admin is False
    assert "WP:GNG" in c.rationale


def test_soft_delete_normalizes_but_keeps_raw_result():
    c = parse_close(SOFT)
    assert c.result == "soft delete"
    assert c.normalized == "soft_delete"


def test_open_discussion_returns_none():
    assert parse_close(OPEN) is None
