"""
src/tools/tavily.py — Tavily: web research for primary source fetch

Role in routing: CORE web research tool. Powers the News Digestor's primary-source lookup:
  - Earnings call capex language (primary source for capex_cut_signal)
  - Fed statement language (primary source for fed_path)
  - Supply-chain tells from trade press (primary source for supply_tell_signal)
  - Korea/China semiconductor news (English-language version)
Key: TAVILY_API_KEY (free tier available).

Returns: list of SearchResult (url, title, content snippet, publish date)
The News Digestor's NLP grader then reads these to score capex_cut_signal and supply_tell_signal.
These are NOT fed raw to the LLM — the orchestrator summarises heavy payloads first.

Run standalone: python -m src.tools.tavily
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from ._env import get_key, load_env

load_env()

import httpx

_BASE = "https://api.tavily.com"


@dataclass
class SearchResult:
    url: str
    title: str
    content: str        # snippet / extract (not full article — respect copyright)
    published: Optional[dt.datetime]
    relevance_score: float


def _key() -> str:
    k = get_key("TAVILY_API_KEY")
    if not k:
        raise EnvironmentError("TAVILY_API_KEY not set")
    return k


def search(query: str, max_results: int = 5,
           search_depth: str = "advanced",
           include_domains: list[str] | None = None,
           exclude_domains: list[str] | None = None) -> list[SearchResult]:
    """
    General Tavily search. Returns up to max_results SearchResults.
    `search_depth`: "basic" (fast) or "advanced" (deeper, uses more quota).
    """
    payload = {
        "api_key": _key(),
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    try:
        r = httpx.post(f"{_BASE}/search", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        pub = None
        pub_str = item.get("published_date") or item.get("published") or ""
        if pub_str:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%B %d, %Y"):
                try:
                    pub = dt.datetime.strptime(pub_str[:len(fmt)+4], fmt)
                    break
                except ValueError:
                    continue
        results.append(SearchResult(
            url=item.get("url", ""),
            title=item.get("title", ""),
            content=item.get("content", "")[:500],   # cap snippet for token efficiency
            published=pub,
            relevance_score=float(item.get("score", 0.5)),
        ))
    return results


# --------------------------------------------------------------------------- #
# Pre-built queries for the News Digestor subagent
# --------------------------------------------------------------------------- #
def capex_cut_search(company: str, quarters_back: int = 2) -> list[SearchResult]:
    """
    Search for earnings call commentary on capital expenditure guidance cuts.
    This feeds the capex_cut_signal grader — the most important News Digestor output.
    """
    return search(
        query=f"{company} capital expenditure guidance cut reduce AI infrastructure spending "
              f"earnings call {dt.date.today().year}",
        max_results=5, search_depth="advanced",
        include_domains=["seekingalpha.com", "fool.com", "ir.microsoft.com", "abc.xyz",
                         "investor.amazon.com", "investor.fb.com", "oracle.com"]
    )


def supply_tell_search(tickers: list[str]) -> list[SearchResult]:
    """
    Search for memory/chip supply catching demand: SK Hynix HBM→DRAM shift, NAND glut, etc.
    Feeds supply_tell_signal.
    """
    semi_str = " OR ".join(tickers[:5])
    return search(
        query=f"({semi_str}) supply oversupply inventory build HBM DRAM NAND order cut "
              f"semiconductor {dt.date.today().year}",
        max_results=6, search_depth="advanced",
    )


def asia_semiconductor_news(basket_names: list[str]) -> list[SearchResult]:
    """
    English-language coverage of Korea/China/Taiwan semiconductor news.
    Asia session runs first — these can be leading indicators before US open.
    """
    companies = " OR ".join(basket_names[:6])   # "SK Hynix OR Samsung OR TSMC OR ..."
    return search(
        query=f"({companies}) earnings guidance chip demand AI spending Korea Japan "
              f"Taiwan semiconductor {dt.date.today().year}",
        max_results=8, search_depth="advanced",
        include_domains=["reuters.com", "bloomberg.com", "ft.com", "nikkei.com",
                         "kedainews.com", "techcrunch.com", "thechipletter.com"]
    )


def fed_statement_search() -> list[SearchResult]:
    """Pull latest Fed commentary for fed_path input."""
    return search(
        query=f"Federal Reserve rate hike cut FOMC statement inflation {dt.date.today().year}",
        max_results=4, search_depth="advanced",
        include_domains=["federalreserve.gov", "wsj.com", "ft.com", "reuters.com"]
    )


if __name__ == "__main__":
    try:
        print("Testing capex_cut_search for Microsoft...")
        results = capex_cut_search("Microsoft")
        for r in results:
            print(f"  [{r.relevance_score:.2f}] {r.title[:60]} — {r.url}")
            print(f"    snippet: {r.content[:120]}...")
        print(f"\n{len(results)} results. Tavily client OK.")
    except EnvironmentError as e:
        print(f"  {e} — set TAVILY_API_KEY in .env")
