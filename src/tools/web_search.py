from duckduckgo_search import DDGS

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_WEB_SEARCH_RETRY_WAIT = wait_exponential(multiplier=0.01, min=0, max=0.05)


class WebSearchRetryableError(RuntimeError):
    """Raised when DuckDuckGo search fails transiently."""


def _call_context_method(method, client, *args):
    """Call context-manager helpers from bound methods or plain function attributes."""
    try:
        return method(*args)
    except TypeError:
        return method(client, *args)


@retry(
    stop=stop_after_attempt(3),
    wait=_WEB_SEARCH_RETRY_WAIT,
    retry=retry_if_exception_type(WebSearchRetryableError),
    reraise=True,
)
def _search_with_retry(query: str, max_results: int) -> str:
    """Execute the DuckDuckGo search with narrow retry coverage."""
    try:
        client = DDGS()
        enter = getattr(client, "__enter__", None)
        exit_ = getattr(client, "__exit__", None)
        ddgs = _call_context_method(enter, client) if callable(enter) else client
        try:
            results = list(ddgs.text(query, max_results=max_results))
        finally:
            if callable(exit_):
                _call_context_method(exit_, client, None, None, None)
    except Exception as exc:
        raise WebSearchRetryableError(str(exc)) from exc

    if not results:
        return "No results found."

    formatted = []
    for r in results:
        formatted.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
    return "\n\n".join(formatted)

def search_web(query: str, max_results: int = 3) -> str:
    """
    Searches the web using DuckDuckGo to find real-time information.
    Args:
        query: The search query.
        max_results: The maximum number of results to return.
    """
    try:
        return _search_with_retry(query, max_results)
    except Exception as e:
        return f"Search Error: {str(e)}"
