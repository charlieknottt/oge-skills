#!/usr/bin/env python3
"""
Deterministic grounding check. A review/provenance agent may only claim an attribute is `stated` in
the scenario if it supplies a verbatim quote. This script exact-substring-matches every claimed quote
against the raw scenario text; a non-matching quote is auto-failed as a fabrication. This is what makes
grounding an EXTERNAL arbiter (a string that either exists in the doc or doesn't), not a model prior —
the single most important decorrelator in the whole design.

Matching is whitespace-normalized and case-insensitive (models paraphrase spacing/case, not words).
A quote must appear as a contiguous span after that normalization, or it fails.

Usage (library): from verify_quotes import verify_quote, load_scenario
Usage (CLI):     python3 verify_quotes.py SCENARIO.md --claims claims.json
  where claims.json = [{"id":..., "quote":"..."}]; prints pass/fail per claim.
"""
import argparse
import json
import re
import sys


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def load_scenario(path):
    return _norm(open(path, encoding="utf-8", errors="replace").read())


def verify_quote(quote, scenario_norm, min_len=12):
    """True iff `quote` (normalized) is a contiguous span of the normalized scenario and long enough
    to be meaningful. Short quotes are rejected to stop trivial keyword 'grounding'."""
    q = _norm(quote)
    if len(q) < min_len:
        return False
    return q in scenario_norm


def verify_claims(claims, scenario_path):
    sn = load_scenario(scenario_path)
    out = []
    for c in claims:
        ok = verify_quote(c.get("quote", ""), sn)
        out.append({**{k: c.get(k) for k in ("id", "edge_id", "attribute")},
                    "quote": c.get("quote", ""), "verified": ok})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--claims", required=True, help="JSON list of {id, quote}")
    args = ap.parse_args()
    claims = json.load(open(args.claims))
    res = verify_claims(claims, args.scenario)
    n_ok = sum(1 for r in res if r["verified"])
    for r in res:
        print(f"[{'OK ' if r['verified'] else 'FAB'}] {r.get('id') or r.get('edge_id')}: {r['quote'][:70]}")
    print(f"\n{n_ok}/{len(res)} quotes verified against {args.scenario}")
    sys.exit(0 if n_ok == len(res) else 1)


if __name__ == "__main__":
    main()
