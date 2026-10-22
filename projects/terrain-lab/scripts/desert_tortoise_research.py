#!/usr/bin/env python3
"""Collect recent desert tortoise research metadata from scholarly APIs."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from urllib.robotparser import RobotFileParser

TERMS = (
    "desert tortoise",
    "Gopherus agassizii",
    "Gopherus morafkai",
    "Gopherus evgoodei",
    "Mojave tortoise",
    "Sonoran tortoise",
)
MATCHES = tuple(x.lower() for x in TERMS) + (
    "agassiz's desert tortoise",
    "morafka's desert tortoise",
    "goode's thornscrub tortoise",
    "sinaloan desert tortoise",
    "mohave desert tortoise",
)
PAPER_TYPES = {"article", "journal-article", "posted-content", "preprint", "review"}


def user_agent(email: str) -> str:
    return "DesertTortoiseResearch/1.0" + (f" (mailto:{email})" if email else "")


def clean(value: object) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def date_from_parts(parts: object) -> str:
    try:
        p = parts[0]
        return dt.date(int(p[0]), int(p[1]) if len(p) > 1 else 1,
                       int(p[2]) if len(p) > 2 else 1).isoformat()
    except (ValueError, TypeError, IndexError, KeyError):
        return ""


def normalized_doi(doi: object) -> str:
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", str(doi or ""), flags=re.I).strip().lower()


def fetch_json(url: str, params: dict, email: str, retries: int = 2) -> dict:
    url = url + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": user_agent(email), "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            delay = min(int(exc.headers.get("Retry-After", "0") or 0), 30) or 2 ** attempt
        except (URLError, TimeoutError):
            if attempt == retries:
                raise
            delay = 2 ** attempt
        time.sleep(delay)
    return {}


def openalex_abstract(index: object) -> str:
    if not isinstance(index, dict):
        return ""
    words = [(int(pos), word) for word, positions in index.items() for pos in positions]
    return " ".join(word for _, word in sorted(words))


def collect_openalex(term: str, since: str, size: int, email: str, key: str) -> list[dict]:
    params = {"search": term, "filter": f"from_publication_date:{since}",
              "sort": "publication_date:desc", "per_page": size,
              "select": "id,display_name,doi,publication_date,type,authorships,primary_location,abstract_inverted_index,is_retracted,open_access"}
    if key:
        params["api_key"] = key
    out = []
    for item in fetch_json("https://api.openalex.org/works", params, email).get("results", []):
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        oa = item.get("open_access") or {}
        out.append({"title": clean(item.get("display_name")), "date": item.get("publication_date") or "",
                    "doi": normalized_doi(item.get("doi")), "url": item.get("doi") or item.get("id") or "",
                    "authors": "; ".join(a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])),
                    "journal": source.get("display_name") or "", "abstract": openalex_abstract(item.get("abstract_inverted_index")),
                    "paper_type": item.get("type") or "", "open_access_url": oa.get("oa_url") or "",
                    "retracted": bool(item.get("is_retracted")), "sources": ["OpenAlex"]})
    return out


def collect_crossref(term: str, since: str, size: int, email: str) -> list[dict]:
    params = {"query.bibliographic": term, "filter": f"from-pub-date:{since}",
              "sort": "published", "order": "desc", "rows": size,
              "select": "DOI,title,published,published-online,published-print,author,container-title,abstract,type,URL"}
    if email:
        params["mailto"] = email
    items = fetch_json("https://api.crossref.org/works", params, email).get("message", {}).get("items", [])
    out = []
    for item in items:
        date = date_from_parts((item.get("published-online") or item.get("published") or item.get("published-print") or {}).get("date-parts"))
        doi = normalized_doi(item.get("DOI"))
        out.append({"title": clean((item.get("title") or [""])[0]), "date": date, "doi": doi,
                    "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                    "authors": "; ".join(" ".join(filter(None, (a.get("given"), a.get("family")))) for a in item.get("author", [])),
                    "journal": clean((item.get("container-title") or [""])[0]), "abstract": clean(item.get("abstract")),
                    "paper_type": item.get("type") or "", "open_access_url": "", "retracted": False,
                    "sources": ["Crossref"]})
    return out


def collect_europepmc(term: str, since: str, size: int, email: str) -> list[dict]:
    query = f'("{term}") AND FIRST_PDATE:[{since} TO *] sort_date:y'
    params = {"query": query, "format": "json", "resultType": "core", "pageSize": size}
    items = fetch_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params, email).get("resultList", {}).get("result", [])
    out = []
    for item in items:
        doi = normalized_doi(item.get("doi"))
        identifier = item.get("id") or ""
        url = f"https://doi.org/{doi}" if doi else (f"https://europepmc.org/article/{item.get('source', 'MED')}/{identifier}" if identifier else "")
        out.append({"title": clean(item.get("title")), "date": item.get("firstPublicationDate") or item.get("firstIndexDate") or "",
                    "doi": doi, "url": url, "authors": clean(item.get("authorString")),
                    "journal": clean(item.get("journalTitle")), "abstract": clean(item.get("abstractText")),
                    "paper_type": "journal-article", "open_access_url": item.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url", "") if item.get("fullTextUrlList", {}).get("fullTextUrl") else "",
                    "retracted": False, "sources": ["Europe PMC"]})
    return out


def relevance(paper: dict) -> int:
    title = paper["title"].lower()
    abstract = paper["abstract"].lower()
    title_hits = sum(term in title for term in MATCHES)
    abstract_hits = sum(term in abstract for term in MATCHES)
    return min(10, title_hits * 5 + abstract_hits * 2)


def deduplicate(papers: list[dict], since: str) -> list[dict]:
    since_date = dt.date.fromisoformat(since)
    today = dt.date.today()
    merged: list[dict] = []
    for p in papers:
        try:
            publication_date = dt.date.fromisoformat(p["date"])
        except (TypeError, ValueError):
            continue
        if not p["title"] or not since_date <= publication_date <= today or p["retracted"]:
            continue
        if p["paper_type"] and p["paper_type"] not in PAPER_TYPES:
            continue
        title = p["title"].lower()
        if re.search(r"\b(?:testudo|chelonoidis|procolophon)\s+[a-z]+", title) and not any(
            term in title for term in ("gopherus", "mojave desert tortoise", "sonoran desert tortoise")
        ):
            continue
        score = relevance(p)
        if score < 4:
            continue
        doi = normalized_doi(p.get("doi"))
        title_key = re.sub(r"\W+", "", title)
        current = next((item for item in merged if doi and item["doi"] == doi), None)
        if current is None:
            current = next((item for item in merged if
                            re.sub(r"\W+", "", item["title"].lower()) == title_key and
                            (not doi or not item["doi"])), None)
        if current is None:
            merged.append({**p, "doi": doi})
        else:
            current["sources"] = sorted(set(current["sources"] + p["sources"]))
            for field in ("abstract", "authors", "journal", "open_access_url", "url"):
                if len(str(p.get(field) or "")) > len(str(current.get(field) or "")):
                    current[field] = p[field]
            if doi and not current["doi"]:
                current["doi"] = doi
            if p["date"] < current["date"]:
                current["date"] = p["date"]
    for p in merged:
        p["relevance_score"] = relevance(p)
    return sorted(merged, key=lambda p: (p["date"], p["relevance_score"]), reverse=True)


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        data = dict(attrs)
        name = (data.get("name") or data.get("property") or "").lower()
        if name and data.get("content"):
            self.metadata[name] = clean(data["content"])


def scrape_abstract(url: str, email: str, robots_cache: dict[str, RobotFileParser]) -> str:
    """Read public HTML citation metadata only when robots.txt permits it."""
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(NoRedirect)
    agent = user_agent(email)
    page = ""
    for _ in range(6):
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return ""
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in robots_cache:
            robots = RobotFileParser(origin + "/robots.txt")
            try:
                robots.read()
            except (OSError, URLError):
                return ""
            robots_cache[origin] = robots
        if not robots_cache[origin].can_fetch(agent, url):
            return ""
        try:
            with opener.open(Request(url, headers={"User-Agent": agent, "Accept": "text/html"}), timeout=15) as response:
                if "html" not in response.headers.get("Content-Type", "").lower():
                    return ""
                page = response.read(1_000_000).decode("utf-8", "replace")
                break
        except HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                url = urljoin(url, exc.headers["Location"])
                continue
            return ""
        except (URLError, TimeoutError, ValueError):
            return ""
    if not page:
        return ""
    parser = MetadataParser()
    parser.feed(page)
    for key in ("citation_abstract", "dc.description", "dcterms.abstract", "description", "og:description"):
        value = parser.metadata.get(key, "")
        if len(value) >= 80:
            return value
    return ""


def export(papers: list[dict], prefix: Path, since: str, failures: list[str]) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    fields = ["date", "title", "authors", "journal", "doi", "url", "open_access_url", "abstract", "relevance_score", "sources"]
    with prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for p in papers:
            writer.writerow({field: "; ".join(p["sources"]) if field == "sources" else p.get(field, "") for field in fields})
    prefix.with_suffix(".json").write_text(json.dumps({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "since": since, "count": len(papers), "source_errors": failures, "papers": papers}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Recent desert tortoise research", "", f"Published since {since}. {len(papers)} papers found.", ""]
    if failures:
        lines += ["Some sources could not be reached: " + "; ".join(failures), ""]
    for p in papers:
        lines += [f"- **{p['date']} — [{p['title']}]({p['url']})**", f"  {p['authors']} · {p['journal']} · {', '.join(p['sources'])}", ""]
    prefix.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=365 * 3)).isoformat(), help="Earliest publication date (YYYY-MM-DD); default: three years ago")
    parser.add_argument("--limit", type=int, default=50, help="Maximum papers in output")
    parser.add_argument("--per-query", type=int, default=25, help="Maximum results per species term and API")
    parser.add_argument("--email", default=os.getenv("RESEARCH_CONTACT_EMAIL", ""), help="Optional contact email for API etiquette")
    parser.add_argument("--openalex-key", default=os.getenv("OPENALEX_API_KEY", ""), help="Optional OpenAlex API key")
    parser.add_argument("--scrape-abstracts", action="store_true", help="Fill missing abstracts from permitted public HTML metadata")
    parser.add_argument("--output-prefix", type=Path, default=Path("desert_tortoise_papers"))
    args = parser.parse_args(argv)
    try:
        dt.date.fromisoformat(args.since)
    except ValueError:
        parser.error("--since must be YYYY-MM-DD")
    if args.limit < 1 or not 1 <= args.per_query <= 100:
        parser.error("--limit must be positive and --per-query must be 1–100")

    papers: list[dict] = []
    failures: list[str] = []
    for name, collector in (("OpenAlex", collect_openalex), ("Crossref", collect_crossref), ("Europe PMC", collect_europepmc)):
        for term in TERMS:
            try:
                found = collector(term, args.since, args.per_query, args.email, args.openalex_key) if name == "OpenAlex" else collector(term, args.since, args.per_query, args.email)
                papers.extend(found)
            except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
                failures.append(f"{name} / {term}: {exc}")
            time.sleep(0.15)
    result = deduplicate(papers, args.since)[:args.limit]
    if args.scrape_abstracts:
        robots_cache: dict[str, RobotFileParser] = {}
        for p in result:
            if not p["abstract"] and p["url"]:
                p["abstract"] = scrape_abstract(p["url"], args.email, robots_cache)
                p["relevance_score"] = relevance(p)
    export(result, args.output_prefix, args.since, failures)
    print(f"Saved {len(result)} papers to {args.output_prefix}.csv, .json, and .md")
    if failures:
        print(f"Warning: {len(failures)} API requests failed; see JSON output.", file=sys.stderr)
    return 0 if papers or not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
