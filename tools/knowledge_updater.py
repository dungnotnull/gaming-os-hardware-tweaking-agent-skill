"""
knowledge_updater.py — Skill 204: gaming-os-hardware-tweaking
Production-grade crawl pipeline: fetches latest papers + news → scores →
appends to SECOND-KNOWLEDGE-BRAIN.md.

Dependencies: pip install requests feedparser python-dateutil
Usage:
    python tools/knowledge_updater.py [--dry-run] [--news-only] [--keywords ...]
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None  # type: ignore

try:
    import feedparser
except ImportError:
    feedparser = None  # type: ignore

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None  # type: ignore

LOG_FILE = Path(__file__).parent.parent / "logs" / "knowledge_update.log"

KNOWLEDGE_CONFIG: Dict[str, Any] = {
    "domain": "Gaming System Optimization & Input Latency Tuning",
    "keywords": [
        "gaming OS tweaking low latency",
        "NVIDIA Reflex input latency optimization",
        "VRR BFI variable refresh rate blur reduction gaming",
        "frame time 1% low consistency stutter",
        "CPU GPU scheduling background process gaming",
        "RAM NVMe paging gaming performance",
        "GPU driver optimization shader cache latency",
        "display latency measurement high-speed camera",
        "input lag mouse keyboard polling rate optimization",
        "DLSS frame generation latency tradeoff",
    ],
    "arxiv_categories": [
        "cs.HC",
        "cs.GR",
        "cs.PF",
        "cs.OS",
    ],
    "arxiv_base": "https://export.arxiv.org/api/query",
    "semantic_scholar_base": "https://api.semanticscholar.org/graph/v1/paper/search",
    "core_ac_uk_base": "https://api.core.ac.uk/v3/search/works",
    "rss_feeds": [
        "https://www.blurbusters.com/feed/",
        "https://www.nvidia.com/en-us/geforce/news/feed/",
    ],
    "authoritative_docs": [
        "IEEE Transactions on Visualization & Computer Graphics",
        "ACM CHI (latency research)",
        "Computers in Human Behavior — Elsevier",
        "Entertainment Computing — Elsevier",
        "Performance Evaluation — Elsevier",
        "Journal of Network and Computer Applications",
    ],
    "scoring_weights": {
        "recency": 0.35,
        "keyword_relevance": 0.35,
        "citation_count": 0.15,
        "source_authority": 0.15,
    },
    "max_results_per_source": 10,
    "max_new_entries_per_run": 20,
    "rate_limit_delay_seconds": 1.0,
    "user_agent": "gaming-os-hardware-tweaking/1.0.0 academic-research-bot",
    "cache_ttl_hours": 24,
}

SOURCE_AUTHORITY_WEIGHTS = {
    "arxiv": 0.5,
    "semantic_scholar": 0.65,
    "core_ac_uk": 0.7,
    "rss": 0.2,
    "manual": 0.9,
}

BRAIN_PATH = Path(__file__).parent.parent / "SECOND-KNOWLEDGE-BRAIN.md"
CACHE_DIR = Path(__file__).parent.parent / "logs" / ".knowledge_cache"
UPDATE_LOG = Path(__file__).parent.parent / "logs" / "update_log.json"

_session_store: Dict[int, requests.Session] = {}
_session_lock = threading.Lock()
_rate_limiter_lock = threading.Lock()
_last_request_time: float = 0.0


def _get_session() -> Optional[Any]:
    if requests is None:
        return None
    tid = threading.get_ident()
    if tid not in _session_store:
        with _session_lock:
            if tid not in _session_store:
                session = requests.Session()
                retry_strategy = Retry(
                    total=5,
                    backoff_factor=2.0,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"],
                )
                adapter = HTTPAdapter(
                    max_retries=retry_strategy,
                    pool_connections=10,
                    pool_maxsize=10,
                )
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                session.headers.update({
                    "User-Agent": KNOWLEDGE_CONFIG["user_agent"],
                    "Accept": "application/json, application/xml, text/xml, */*",
                })
                _session_store[tid] = session
    return _session_store[tid]


def _rate_limit():
    global _last_request_time
    delay = KNOWLEDGE_CONFIG.get("rate_limit_delay_seconds", 1.0)
    with _rate_limiter_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < delay:
            jitter = random.uniform(0, delay * 0.5)
            time.sleep(delay - elapsed + jitter)
        _last_request_time = time.monotonic()


def fetch_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 5,
    base_delay: float = 2.0,
    timeout: int = 30,
) -> Optional[requests.Response]:
    if requests is None:
        _log("ERROR", "requests library not available")
        return None

    session = _get_session()
    if session is None:
        return None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = base_delay * (2 ** attempt)
                _log("INFO", f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s")
                time.sleep(delay)
            else:
                _rate_limit()

            resp = session.get(url, params=params or {}, timeout=timeout)

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                _log("WARN", f"Rate limited (429). Waiting {wait:.1f}s")
                time.sleep(wait)
                if attempt < max_retries - 1:
                    continue
                return None

            if resp.status_code >= 500:
                _log("WARN", f"Server error {resp.status_code} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    continue
                return None

            if resp.status_code == 404:
                _log("WARN", f"Not found: {url}")
                return None

            resp.raise_for_status()
            return resp

        except requests.exceptions.Timeout:
            _log("WARN", f"Timeout fetching {url} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                continue
        except requests.exceptions.ConnectionError as e:
            _log("WARN", f"Connection error: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                continue
        except requests.exceptions.RequestException as e:
            _log("WARN", f"Request failed: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                continue
        except Exception as e:
            _log("ERROR", f"Unexpected error: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                continue

    return None


def compute_hash(identifier: str) -> str:
    return hashlib.sha256(
        identifier.strip().lower().encode("utf-8")
    ).hexdigest()


def load_existing_hashes() -> Set[str]:
    if not BRAIN_PATH.exists():
        return set()
    hashes: Set[str] = set()
    try:
        content = BRAIN_PATH.read_text(encoding="utf-8")
        for m in re.finditer(r"\*\*DOI/URL:\*\*\s*(\S+)", content):
            hashes.add(compute_hash(m.group(1)))
        for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", content):
            hashes.add(compute_hash(m.group(2)))
    except Exception as e:
        _log("ERROR", f"Failed to read brain: {e}")
    return hashes


def load_cache() -> Dict[str, Any]:
    if not CACHE_DIR.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "fetch_cache.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            cache_time = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            ttl = timedelta(hours=KNOWLEDGE_CONFIG.get("cache_ttl_hours", 24))
            if datetime.now() - cache_time < ttl:
                return data.get("entries", {})
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return {}


def save_cache(entries: Dict[str, Any]):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "fetch_cache.json"
    cache_file.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "entries": entries,
    }, indent=2))


def score_entry(
    entry: Dict[str, Any],
    keywords: List[str],
    now: Optional[datetime] = None,
) -> float:
    if now is None:
        now = datetime.now()

    recency = 0.0
    pub = entry.get("published_date")
    if pub is not None:
        try:
            if isinstance(pub, datetime):
                days = (now - pub).days
            else:
                days = (now - dateutil_parser.parse(str(pub))).days if dateutil_parser else 365
            recency = max(0.0, 1.0 - days / 730.0)
        except Exception:
            recency = 0.0

    text = " ".join([
        str(entry.get("title", "")),
        str(entry.get("abstract", "")),
        str(entry.get("venue", "")),
    ]).lower()

    keyword_hits = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in text:
            keyword_hits += 1
        else:
            kw_words = kw_lower.split()
            if len(kw_words) > 1 and sum(1 for w in kw_words if w in text) >= len(kw_words) / 2:
                keyword_hits += 0.5
    relevance = min(keyword_hits / max(len(keywords), 1), 1.0)

    cit = entry.get("citation_count", 0) or 0
    cit_score = min(math.log1p(cit) / math.log1p(1000), 1.0) if cit > 0 else 0.0

    source = entry.get("source", "unknown")
    source_weight = SOURCE_AUTHORITY_WEIGHTS.get(source, 0.3)

    w = KNOWLEDGE_CONFIG["scoring_weights"]
    composite = (
        recency * w["recency"]
        + relevance * w["keyword_relevance"]
        + cit_score * w["citation_count"]
        + source_weight * w["source_authority"]
    )
    return round(composite * 10.0, 2)


def _log(level: str, message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}\n"
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line.strip())


def fetch_arxiv(keywords: List[str]) -> List[Dict[str, Any]]:
    if requests is None:
        return []
    cats = KNOWLEDGE_CONFIG.get("arxiv_categories", [])
    if not cats:
        return []

    results: List[Dict[str, Any]] = []

    for cat in cats:
        q = f'cat:{cat} AND ({" OR ".join(f"all:{kw}" for kw in keywords[:5])})'
        resp = fetch_with_retry(
            KNOWLEDGE_CONFIG["arxiv_base"],
            params={
                "search_query": q,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": KNOWLEDGE_CONFIG["max_results_per_source"],
            },
        )
        if resp is None:
            continue

        try:
            import xml.etree.ElementTree as ET
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(resp.content)
        except Exception as e:
            _log("WARN", f"ArXiv XML parse failed: {e}")
            continue

        for entry in root.findall("atom:entry", ns):
            t = entry.find("atom:title", ns)
            s = entry.find("atom:summary", ns)
            i = entry.find("atom:id", ns)
            p = entry.find("atom:published", ns)

            title = (t.text or "").strip().replace("\n", " ") if t is not None else ""
            url = (i.text or "").strip() if i is not None else ""

            if not title or not url:
                continue

            pub = None
            if p is not None and p.text:
                try:
                    pub = dateutil_parser.parse(p.text).replace(tzinfo=None) if dateutil_parser else None
                except Exception:
                    pass

            authors_el = entry.findall("atom:author", ns)
            authors = [
                (a.find("atom:name", ns).text or "").strip()
                for a in authors_el
                if a.find("atom:name", ns) is not None
            ][:3]

            results.append({
                "title": title,
                "authors": authors or ["Unknown"],
                "year": pub.year if pub else datetime.now().year,
                "venue": f"ArXiv ({cat})",
                "doi_or_url": url,
                "abstract": (s.text or "")[:500] if s is not None else "",
                "published_date": pub,
                "citation_count": 0,
                "source": "arxiv",
            })
        time.sleep(0.5)

    _log("INFO", f"ArXiv: fetched {len(results)} papers")
    return results


def fetch_semantic_scholar(keywords: List[str]) -> List[Dict[str, Any]]:
    if requests is None:
        return []

    results: List[Dict[str, Any]] = []
    query_terms = keywords[:4] if len(keywords) > 4 else keywords

    for term in query_terms:
        resp = fetch_with_retry(
            KNOWLEDGE_CONFIG["semantic_scholar_base"],
            params={
                "query": term,
                "fields": "title,authors,year,venue,externalIds,abstract,citationCount,publicationDate",
                "limit": max(3, KNOWLEDGE_CONFIG["max_results_per_source"] // 4),
            },
        )
        if resp is None:
            continue

        try:
            data = resp.json()
        except Exception as e:
            _log("WARN", f"Semantic Scholar JSON parse failed: {e}")
            continue

        for p in data.get("data", []):
            title = p.get("title", "")
            if not title:
                continue

            year = p.get("year") or datetime.now().year
            ext = p.get("externalIds", {}) or {}
            doi = ext.get("DOI") or (
                f"https://arxiv.org/abs/{ext['ArXiv']}" if ext.get("ArXiv") else ""
            )
            if not doi:
                paper_id = p.get("paperId", "")
                if paper_id:
                    doi = f"https://www.semanticscholar.org/paper/{paper_id}"

            pub = None
            pub_date_str = p.get("publicationDate")
            if pub_date_str and dateutil_parser:
                try:
                    pub = dateutil_parser.parse(pub_date_str).replace(tzinfo=None)
                except Exception:
                    pub = datetime(year, 1, 1)
            else:
                pub = datetime(year, 1, 1)

            results.append({
                "title": title,
                "authors": [a.get("name", "Unknown") for a in p.get("authors", [])[:3]],
                "year": year,
                "venue": p.get("venue") or "Unknown",
                "doi_or_url": doi,
                "abstract": (p.get("abstract") or "")[:500],
                "published_date": pub,
                "citation_count": p.get("citationCount", 0),
                "source": "semantic_scholar",
            })
        time.sleep(0.5)

    _log("INFO", f"Semantic Scholar: fetched {len(results)} papers")
    return results


def fetch_core_ac_uk(keywords: List[str]) -> List[Dict[str, Any]]:
    api_key = os.environ.get("CORE_API_KEY", "")
    if not api_key or requests is None:
        return []

    results: List[Dict[str, Any]] = []
    query = " OR ".join(keywords[:4])

    resp = fetch_with_retry(
        KNOWLEDGE_CONFIG["core_ac_uk_base"],
        params={"q": query, "limit": KNOWLEDGE_CONFIG["max_results_per_source"]},
    )
    if resp is None:
        return results

    try:
        data = resp.json()
    except Exception:
        return results

    for p in data.get("results", []):
        title = p.get("title", "")
        if not title:
            continue

        doi = p.get("doi") or p.get("downloadUrl", "")
        pub = None
        pub_date = p.get("publishedDate") or p.get("datePublished")
        if pub_date and dateutil_parser:
            try:
                pub = dateutil_parser.parse(pub_date).replace(tzinfo=None)
            except Exception:
                pass

        results.append({
            "title": title,
            "authors": [a.get("name", "Unknown") for a in p.get("authors", [])[:3]],
            "year": pub.year if pub else datetime.now().year,
            "venue": p.get("publisher") or "CORE",
            "doi_or_url": doi,
            "abstract": (p.get("abstract") or "")[:500],
            "published_date": pub,
            "citation_count": p.get("citationCount", 0),
            "source": "core_ac_uk",
        })

    _log("INFO", f"CORE.ac.uk: fetched {len(results)} papers")
    return results


def fetch_rss() -> List[Dict[str, Any]]:
    if feedparser is None:
        return []
    feeds = KNOWLEDGE_CONFIG.get("rss_feeds", [])
    if not feeds:
        return []

    results: List[Dict[str, Any]] = []
    for url in feeds:
        try:
            _rate_limit()
            feed = feedparser.parse(url)
        except Exception as e:
            _log("WARN", f"RSS parse failed for {url}: {e}")
            continue

        if feed.bozo and not feed.entries:
            _log("WARN", f"RSS feed {url} is malformed")
            continue

        for item in feed.entries[:15]:
            title = item.get("title", "")
            link = item.get("link", "")
            if not title or not link:
                continue

            pub_parsed = item.get("published_parsed")
            if pub_parsed:
                pub = datetime(*pub_parsed[:6])
            else:
                pub = datetime.now()

            summary = item.get("summary", "") or item.get("description", "")
            import html
            summary = html.unescape(re.sub(r"<[^>]+>", "", str(summary)))[:300]

            results.append({
                "title": title.strip(),
                "authors": [item.get("author", "Editorial")],
                "year": pub.year,
                "venue": item.get("source", {}).get("title", "RSS") if hasattr(item, "source") else "RSS",
                "doi_or_url": link,
                "abstract": summary,
                "published_date": pub,
                "citation_count": 0,
                "source": "rss",
            })

    _log("INFO", f"RSS: fetched {len(results)} items")
    return results


def format_entry(entry: Dict[str, Any], score: float) -> str:
    d = datetime.now().strftime("%Y-%m-%d")
    authors = ", ".join(entry.get("authors", [])) or "Unknown"
    return (
        f"\n### {d} — {entry.get('title', 'Untitled')}\n"
        f"- **Authors:** {authors}\n"
        f"- **Year:** {entry.get('year', '')}\n"
        f"- **Venue:** {entry.get('venue', 'Unknown')}\n"
        f"- **DOI/URL:** {entry.get('doi_or_url', '')}\n"
        f"- **Relevance Score:** {score}/10\n"
        f"- **Source Type:** {entry.get('source', 'unknown')}\n"
        f"- **Key Finding:** {entry.get('abstract', 'No abstract available.')}\n"
        f"- **Citations:** {entry.get('citation_count', 0)}\n"
    )


def append_to_brain(entries: List[Dict[str, Any]], dry_run: bool = False) -> int:
    if not BRAIN_PATH.exists():
        _log("ERROR", f"Brain file not found: {BRAIN_PATH}")
        return 0

    existing = load_existing_hashes()
    now = datetime.now()

    new_entries: List[Dict[str, Any]] = []
    seen_titles: Set[str] = set()

    for e in entries:
        doi = e.get("doi_or_url", "")
        if not doi:
            continue

        h = compute_hash(doi)
        if h in existing:
            continue

        title_hash = compute_hash(e.get("title", ""))
        if title_hash in seen_titles:
            continue
        seen_titles.add(title_hash)

        existing.add(h)
        new_entries.append(e)

    if not new_entries:
        _log("INFO", "No new entries to append (all deduplicated)")
        return 0

    for e in new_entries:
        e["_score"] = score_entry(e, KNOWLEDGE_CONFIG["keywords"], now)

    new_entries.sort(key=lambda x: x["_score"], reverse=True)
    new_entries = new_entries[:KNOWLEDGE_CONFIG["max_new_entries_per_run"]]

    text = "\n".join(format_entry(e, e["_score"]) for e in new_entries)

    if dry_run:
        _log("DRY", f"Would append {len(new_entries)} entries:")
        for e in new_entries:
            _log("DRY", f"  [{e['_score']:.1f}] {e.get('title', '?')[:80]}")
        return len(new_entries)

    try:
        content = BRAIN_PATH.read_text(encoding="utf-8")
        if "## 7. Knowledge Update Log" in content:
            content += "\n" + text
        else:
            content += "\n## 7. Knowledge Update Log\n" + text
        BRAIN_PATH.write_text(content, encoding="utf-8")

        update_record = {
            "timestamp": datetime.now().isoformat(),
            "entries_added": len(new_entries),
            "entries": [
                {"title": e.get("title", ""), "score": e["_score"], "source": e.get("source", "")}
                for e in new_entries
            ],
        }
        UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing_logs: List[Dict[str, Any]] = []
        if UPDATE_LOG.exists():
            try:
                existing_logs = json.loads(UPDATE_LOG.read_text())
            except Exception:
                existing_logs = []
        existing_logs.append(update_record)
        if len(existing_logs) > 50:
            existing_logs = existing_logs[-50:]
        UPDATE_LOG.write_text(json.dumps(existing_logs, indent=2))

        _log("INFO", f"Appended {len(new_entries)} entries to knowledge base")
    except Exception as e:
        _log("ERROR", f"Failed to write brain: {e}")
        return 0

    return len(new_entries)


def main():
    ap = argparse.ArgumentParser(
        description="gaming-os-hardware-tweaking knowledge updater")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview changes without writing")
    ap.add_argument("--news-only", action="store_true",
                    help="Only fetch RSS feeds, skip academic sources")
    ap.add_argument("--academic-only", action="store_true",
                    help="Only fetch academic sources, skip RSS")
    ap.add_argument("--keywords", nargs="+",
                    default=KNOWLEDGE_CONFIG["keywords"],
                    help="Custom search keywords")
    ap.add_argument("--max-entries", type=int,
                    default=KNOWLEDGE_CONFIG["max_new_entries_per_run"],
                    help="Max entries to append")
    args = ap.parse_args()

    KNOWLEDGE_CONFIG["max_new_entries_per_run"] = args.max_entries

    _log("INFO", f"=== Knowledge Update Started ===")
    _log("INFO", f"Dry run: {args.dry_run}, News only: {args.news_only}, "
                  f"Academic only: {args.academic_only}")

    all_entries: List[Dict[str, Any]] = []
    fetch_errors: List[str] = []

    if not args.news_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fetch_arxiv, args.keywords): "arxiv",
                executor.submit(fetch_semantic_scholar, args.keywords): "semantic_scholar",
                executor.submit(fetch_core_ac_uk, args.keywords): "core_ac_uk",
            }
            for future in concurrent.futures.as_completed(futures):
                source = futures[future]
                try:
                    entries = future.result()
                    all_entries.extend(entries)
                except Exception as e:
                    fetch_errors.append(f"{source}: {e}")
                    _log("ERROR", f"Parallel fetch failed for {source}: {e}")

    if not args.academic_only:
        try:
            rss_entries = fetch_rss()
            all_entries.extend(rss_entries)
        except Exception as e:
            fetch_errors.append(f"rss: {e}")
            _log("ERROR", f"RSS fetch failed: {e}")

    _log("INFO", f"Total candidates fetched: {len(all_entries)}")
    if fetch_errors:
        _log("WARN", f"Fetch errors ({len(fetch_errors)}): {'; '.join(fetch_errors)}")

    n = append_to_brain(all_entries, args.dry_run)
    _log("INFO", f"=== Knowledge Update Complete ({n} entries) ===\n")

    if fetch_errors and n == 0:
        _log("WARN", "No entries added and fetches had errors. Check network connectivity.")


if __name__ == "__main__":
    main()
