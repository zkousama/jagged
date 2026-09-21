import json
from jagged.wiki import WikiClient


class FakeTransport:
    def __init__(self, responses): self.responses, self.calls = responses, []
    def get(self, params):
        self.calls.append(params)
        return self.responses.pop(0)


def test_log_titles_filters_to_discussion_pages(tmp_path):
    t = FakeTransport([{ "parse": {"links": [
        {"*": "Wikipedia:Articles for deletion/Kieran Woolley"},
        {"*": "Wikipedia:Deletion policy"},
        {"*": "Wikipedia:Articles for deletion/Elizabeth Moran (scientist)"},
    ]}}])
    c = WikiClient(tmp_path, transport=t)
    assert c.log_titles("2024 March 3") == [
        "Wikipedia:Articles for deletion/Kieran Woolley",
        "Wikipedia:Articles for deletion/Elizabeth Moran (scientist)",
    ]


def test_wikitext_is_cached_after_first_fetch(tmp_path):
    page = {"query": {"pages": {"1": {"revisions": [
        {"slots": {"main": {"*": "{{Afd top/old}} The result was '''keep'''."}}}]}}}}
    t = FakeTransport([page])
    c = WikiClient(tmp_path, transport=t)
    first = c.wikitext("Wikipedia:Articles for deletion/X")
    second = c.wikitext("Wikipedia:Articles for deletion/X")
    assert first == second == "{{Afd top/old}} The result was '''keep'''."
    assert len(t.calls) == 1, "second call must come from cache"


def test_missing_page_returns_empty_string(tmp_path):
    t = FakeTransport([{"query": {"pages": {"-1": {"missing": ""}}}}])
    c = WikiClient(tmp_path, transport=t)
    assert c.wikitext("Wikipedia:Articles for deletion/Nope") == ""
