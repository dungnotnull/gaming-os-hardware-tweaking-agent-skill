"""
ingest_knowledge.py — One-shot ingestion of an external knowledge file into
SECOND-KNOWLEDGE-BRAIN.md.

Reads a Markdown/text file (or URL content already saved locally), dedups by
SHA-256, scores by keyword relevance, and appends matching entries to a target
section. Designed for periodic manual ingestion of curated research dumps.

Usage:
    python scripts/ingest_knowledge.py --input path/to/dump.md \
        --keywords "latency,reflex,vrr" --section "## 3. State-of-the-Art" \
        [--dry-run] [--brain SECOND-KNOWLEDGE-BRAIN.md]
"""
from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")


def score_text(text: str, keywords: List[str]) -> float:
    if not keywords:
        return 1.0
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw and kw.lower() in lower)
    return hits / len(keywords)


def extract_bullets(content: str) -> List[str]:
    bullets: List[str] = []
    for line in content.splitlines():
        m = BULLET_RE.match(line)
        if m:
            bullets.append(m.group(1).strip())
    return bullets


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a knowledge dump into the brain")
    parser.add_argument("--input", required=True, help="path to local Markdown/text dump")
    parser.add_argument("--keywords", default="", help="comma-separated relevance keywords")
    parser.add_argument("--section", default="## 7. Knowledge Update Log",
                        help="target section heading in the brain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--brain", default="SECOND-KNOWLEDGE-BRAIN.md")
    parser.add_argument("--min-score", type=float, default=0.25,
                        help="minimum relevance score to ingest a bullet")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ingest] input not found: {input_path}")
        return 1
    brain_path = ROOT / args.brain
    if not brain_path.exists():
        print(f"[ingest] brain not found: {brain_path}")
        return 1

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    source_text = input_path.read_text(encoding="utf-8")
    bullets = extract_bullets(source_text)
    if not bullets:
        # Treat each non-empty line as a candidate.
        bullets = [ln.strip() for ln in source_text.splitlines() if ln.strip()]

    brain_text = brain_path.read_text(encoding="utf-8")
    hash_before = hashlib.sha256(brain_text.encode("utf-8")).hexdigest()
    ingested = 0
    skipped = 0

    ts = datetime.now().strftime("%Y-%m-%d")
    new_lines: List[str] = []
    for bullet in bullets:
        if bullet in brain_text:
            skipped += 1
            continue
        score = score_text(bullet, keywords)
        if score < args.min_score:
            skipped += 1
            continue
        new_lines.append(
            f"- [{ts}] (score={score:.2f}, src={input_path.name}) {bullet}"
        )
        ingested += 1

    print(f"[ingest] ingested={ingested} skipped={skipped} (min_score={args.min_score})")
    if args.dry_run or ingested == 0:
        print("[ingest] dry-run or nothing to ingest; not writing")
        return 0

    block = "\n".join(new_lines)
    if args.section in brain_text:
        brain_text = brain_text.replace(args.section, args.section + "\n" + block, 1)
    else:
        brain_text += "\n" + args.section + "\n" + block
    brain_path.write_text(brain_text, encoding="utf-8")
    print(f"[ingest] sha256_before={hash_before}")
    print(f"[ingest] sha256_after ={hashlib.sha256(brain_text.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
