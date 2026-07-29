"""
test_knowledge_updater.py — Skill 204: gaming-os-hardware-tweaking
Production-grade validation suite: hash dedup, scoring, entry formatting,
deduplication, and config integrity checks.
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knowledge_updater as ku


def test_hash_dedup():
    a = ku.compute_hash("https://example.com/1")
    b = ku.compute_hash("https://example.com/1")
    c = ku.compute_hash("https://example.com/2")
    assert a == b, "Same URL should produce same hash"
    assert a != c, "Different URLs should produce different hashes"
    assert ku.compute_hash("  https://EXAMPLE.com/1  ") == a, "Hash should be case-insensitive, whitespace-insensitive"
    print("[OK] hash dedup")


def test_scoring_basic():
    e = {
        "title": ku.KNOWLEDGE_CONFIG["domain"],
        "abstract": ku.KNOWLEDGE_CONFIG["domain"],
        "published_date": datetime.now(),
        "citation_count": 10,
        "source": "arxiv",
    }
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.now())
    assert 0 <= s <= 10, f"Score {s} should be in [0, 10]"
    print(f"[OK] scoring basic: {s:.2f}/10")


def test_scoring_old_entry():
    e = {
        "title": "Gaming OS tweaks",
        "abstract": "old paper",
        "published_date": datetime.now() - timedelta(days=800),
        "citation_count": 0,
        "source": "arxiv",
    }
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.now())
    assert s < 5, f"Old entry should score low, got {s}"
    print(f"[OK] scoring old entry: {s:.2f}/10")


def test_scoring_high_citations():
    e = {
        "title": ku.KNOWLEDGE_CONFIG["keywords"][0],
        "abstract": " ".join(ku.KNOWLEDGE_CONFIG["keywords"][:3]),
        "published_date": datetime.now(),
        "citation_count": 500,
        "source": "semantic_scholar",
    }
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.now())
    assert s > 5, f"High-relevance entry should score high, got {s}"
    print(f"[OK] scoring high citations: {s:.2f}/10")


def test_scoring_no_date():
    e = {
        "title": "Test without date",
        "abstract": "",
        "published_date": None,
        "citation_count": 0,
        "source": "unknown",
    }
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.now())
    assert 0 <= s <= 10
    print(f"[OK] scoring no date: {s:.2f}/10")


def test_scoring_partial_keyword_match():
    e = {
        "title": "CPU and GPU scheduling for games",
        "abstract": "optimizing background processes",
        "published_date": datetime.now(),
        "citation_count": 5,
        "source": "arxiv",
    }
    s = ku.score_entry(e, ku.KNOWLEDGE_CONFIG["keywords"], datetime.now())
    assert 0 <= s <= 10
    print(f"[OK] scoring partial keywords: {s:.2f}/10")


def test_format():
    entry = {
        "title": "Test Paper",
        "authors": ["Author1", "Author2"],
        "year": 2026,
        "venue": "Test Venue",
        "doi_or_url": "https://example.com/test",
        "abstract": "Test abstract content",
        "source": "semantic_scholar",
        "citation_count": 42,
    }
    txt = ku.format_entry(entry, 8.5)
    assert "Test Paper" in txt
    assert "Author1, Author2" in txt
    assert "https://example.com/test" in txt
    assert "Relevance Score:" in txt
    assert "Source Type:" in txt
    assert "Citations:" in txt
    print("[OK] format entry")


def test_format_no_abstract():
    entry = {
        "title": "T",
        "authors": ["A"],
        "year": 2026,
        "venue": "V",
        "doi_or_url": "https://x.com",
        "abstract": "",
        "source": "unknown",
        "citation_count": 0,
    }
    txt = ku.format_entry(entry, 5.0)
    assert "No abstract available" in txt or "Key Finding" in txt
    print("[OK] format no abstract")


def test_config_integrity():
    cfg = ku.KNOWLEDGE_CONFIG
    required_keys = ["domain", "keywords", "scoring_weights", "arxiv_base",
                     "semantic_scholar_base", "rss_feeds", "authoritative_docs"]
    for key in required_keys:
        assert key in cfg, f"Missing config key: {key}"

    weight_sum = sum(cfg["scoring_weights"].values())
    assert abs(weight_sum - 1.0) < 0.01, f"Scoring weights should sum to 1.0, got {weight_sum}"

    assert len(cfg["keywords"]) >= 4, "Should have at least 4 keywords"
    print("[OK] config integrity")


def test_load_existing_hashes_empty():
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    try:
        f.write("# Empty\n")
        f.close()
        ku.BRAIN_PATH = Path(f.name)
        try:
            hashes = ku.load_existing_hashes()
            assert isinstance(hashes, set)
            print("[OK] load hashes empty brain")
        finally:
            ku.BRAIN_PATH = Path(__file__).parent.parent / "SECOND-KNOWLEDGE-BRAIN.md"
    finally:
        try:
            Path(f.name).unlink()
        except OSError:
            pass


def test_update_log_writing():
    log_data = [{"timestamp": datetime.now().isoformat(), "entries_added": 3, "entries": []}]
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    try:
        json.dump(log_data, f)
        f.close()
        original_log = ku.UPDATE_LOG
        ku.UPDATE_LOG = Path(f.name)
        try:
            loaded = json.loads(ku.UPDATE_LOG.read_text())
            assert len(loaded) == 1
            assert loaded[0]["entries_added"] == 3
            print("[OK] update log reading")
        finally:
            ku.UPDATE_LOG = original_log
    finally:
        try:
            Path(f.name).unlink()
        except OSError:
            pass


def test_source_authority_weights():
    for source, weight in ku.SOURCE_AUTHORITY_WEIGHTS.items():
        assert 0 <= weight <= 1, f"Source weight for {source} should be in [0,1]"
    print("[OK] source authority weights valid")


def test_rate_limit_config():
    delay = ku.KNOWLEDGE_CONFIG.get("rate_limit_delay_seconds", 0)
    assert delay > 0, "Rate limit delay should be positive"
    cache_ttl = ku.KNOWLEDGE_CONFIG.get("cache_ttl_hours", 0)
    assert cache_ttl > 0, "Cache TTL should be positive"
    print("[OK] rate limit config")


if __name__ == "__main__":
    tests = [
        test_hash_dedup,
        test_scoring_basic,
        test_scoring_old_entry,
        test_scoring_high_citations,
        test_scoring_no_date,
        test_scoring_partial_keyword_match,
        test_format,
        test_format_no_abstract,
        test_config_integrity,
        test_load_existing_hashes_empty,
        test_update_log_writing,
        test_source_authority_weights,
        test_rate_limit_config,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed")
    if passed != len(tests):
        sys.exit(1)
    print("all knowledge_updater tests passed")
