from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings


SEMANTIC_SCHOLAR_BULK_SEARCH_URL = (
    "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
)
SEMANTIC_SCHOLAR_RELEVANCE_SEARCH_URL = (
    "https://api.semanticscholar.org/graph/v1/paper/search"
)
SEMANTIC_SCHOLAR_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "authors",
        "year",
        "venue",
        "url",
        "citationCount",
        "influentialCitationCount",
        "externalIds",
        "openAccessPdf",
    ]
)


class PaperSearchError(RuntimeError):
    """Actionable paper-search failure exposed to the Agent tool."""


def normalize_semantic_scholar_paper(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Semantic Scholar record into a stable tool payload."""

    authors = [
        author.get("name", "")
        for author in item.get("authors") or []
        if isinstance(author, dict) and author.get("name")
    ]
    external_ids = item.get("externalIds") or {}
    open_access_pdf = item.get("openAccessPdf") or {}
    return {
        "paper_id": item.get("paperId"),
        "title": item.get("title"),
        "authors": authors,
        "year": item.get("year"),
        "venue": item.get("venue"),
        "abstract": item.get("abstract"),
        "citation_count": item.get("citationCount"),
        "influential_citation_count": item.get("influentialCitationCount"),
        "doi": external_ids.get("DOI") if isinstance(external_ids, dict) else None,
        "arxiv_id": external_ids.get("ArXiv") if isinstance(external_ids, dict) else None,
        "url": item.get("url"),
        "open_access_pdf_url": (
            open_access_pdf.get("url")
            if isinstance(open_access_pdf, dict)
            else None
        ),
    }


class PaperSearchClient:
    """Async Semantic Scholar client used by the paper-search Agent tool.

    Bulk search is preferred because Semantic Scholar documents it as the
    lower-cost endpoint for ordinary keyword discovery. If bulk search is
    unavailable, the client falls back once to relevance search.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "EduAgent-Hub/1.2 paper-research",
            "Accept": "application/json",
        }
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key
        return headers

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        body = response.text.strip().replace("\n", " ")[:500]
        suffix = f" body={body}" if body else ""
        if response.status_code == 429:
            return (
                "Semantic Scholar HTTP 429: rate limited. Configure "
                "SEMANTIC_SCHOLAR_API_KEY and retry after a short delay."
                f"{suffix}"
            )
        if response.status_code in {401, 403}:
            return (
                f"Semantic Scholar HTTP {response.status_code}: authentication/"
                "access rejected. Check SEMANTIC_SCHOLAR_API_KEY and whether "
                "the server can access api.semanticscholar.org."
                f"{suffix}"
            )
        return f"Semantic Scholar HTTP {response.status_code}.{suffix}"

    async def _request(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        params: dict[str, str | int],
    ) -> dict[str, Any]:
        response = await client.get(url, params=params, headers=self._headers())
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            delay = 1.2
            if retry_after:
                try:
                    delay = min(max(float(retry_after), 0.5), 5.0)
                except ValueError:
                    pass
            await asyncio.sleep(delay)
            response = await client.get(url, params=params, headers=self._headers())

        if response.is_error:
            raise PaperSearchError(self._error_message(response))

        payload = response.json()
        if not isinstance(payload, dict):
            raise PaperSearchError("Semantic Scholar returned a non-object JSON payload")
        return payload

    async def search(
        self,
        *,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise ValueError("Paper search query cannot be empty")
        if len(query) > 500:
            raise ValueError("Paper search query is too long")

        limit = max(1, min(limit, self.settings.paper_search_max_results))
        params: dict[str, str | int] = {
            "query": query,
            "limit": limit,
            "fields": SEMANTIC_SCHOLAR_FIELDS,
        }
        if year_from is not None or year_to is not None:
            start = str(year_from) if year_from is not None else ""
            end = str(year_to) if year_to is not None else ""
            params["year"] = f"{start}-{end}"

        timeout = httpx.Timeout(self.settings.paper_search_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            errors: list[str] = []
            payload: dict[str, Any] | None = None
            for url in (
                SEMANTIC_SCHOLAR_BULK_SEARCH_URL,
                SEMANTIC_SCHOLAR_RELEVANCE_SEARCH_URL,
            ):
                try:
                    payload = await self._request(client, url=url, params=params)
                    break
                except PaperSearchError as exc:
                    errors.append(str(exc))
                except httpx.TimeoutException as exc:
                    errors.append(f"Semantic Scholar timeout: {type(exc).__name__}")
                except httpx.RequestError as exc:
                    errors.append(
                        "Semantic Scholar network error: "
                        f"{type(exc).__name__}: {str(exc)[:300]}"
                    )

            if payload is None:
                raise PaperSearchError(" | ".join(errors) or "Paper search failed")

        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [
            normalize_semantic_scholar_paper(item)
            for item in data
            if isinstance(item, dict)
        ]
