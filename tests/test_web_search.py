from types import SimpleNamespace

from tenacity import wait_none

import src.tools.web_search as web_search


def test_search_web_formats_results(monkeypatch):
    result_row = {
        "title": "Python",
        "body": "Programming language",
        "href": "https://python.org",
    }
    ddgs = SimpleNamespace(text=lambda query, max_results: [result_row])
    context = SimpleNamespace(
        __enter__=lambda self: ddgs,
        __exit__=lambda self, exc_type, exc, tb: None,
    )
    monkeypatch.setattr(web_search, "DDGS", lambda: context)

    result = web_search.search_web("Python programming", max_results=1)

    assert "Python" in result
    assert "URL: https://python.org" in result


def test_search_web_retries_transient_failure(monkeypatch):
    monkeypatch.setattr(web_search, "_WEB_SEARCH_RETRY_WAIT", wait_none())

    state = {"calls": 0}

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def text(self, query, max_results):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("temporary outage")
            return [{"title": "Python", "body": "Recovered", "href": "https://python.org"}]

    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    result = web_search.search_web("Python programming", max_results=1)

    assert "Recovered" in result
    assert state["calls"] == 2


def test_search_web_no_results(monkeypatch):
    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def text(self, query, max_results):
            return []

    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    result = web_search.search_web("lkjhasdflkjhasdflkjhasdflkjh", max_results=1)

    assert result == "No results found."
