import arxiv

MAX_RESULTS = 5


def search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    client = arxiv.Client(page_size=max_results)
    search_query = arxiv.Search(query=query, max_results=max_results)
    try:
        return [
            {
                "title": result.title,
                "summary": result.summary[:500],
                "url": result.entry_id,
                "published": result.published.isoformat() if result.published else None,
            }
            for result in client.results(search_query)
        ]
    except arxiv.ArxivError as exc:
        raise RuntimeError("arXiv search failed") from exc
