"""Vertical packs: what to look for in a market. One JSON file per pack in data/verticals/.

  id, label, industry     naming and the industry label used for scoring/fit
  sources                 default discovery sources (nppes | places | adzuna | csv | manual)
  tier_order, tiers       ordered groups of search terms: taxonomies (NPPES), places_queries (Google Places), professions (job boards)
"""
import json
import os

DIR = os.path.join(os.path.dirname(__file__), "data", "verticals")


def available():
    return sorted(f[:-5] for f in os.listdir(DIR) if f.endswith(".json"))


def load(pack_id):
    path = os.path.join(DIR, f"{pack_id}.json")
    if not os.path.exists(path):
        raise SystemExit(f"Unknown vertical pack {pack_id!r}. Available: {', '.join(available())}.")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def terms(pack, kind, tiers=None):
    """Search terms of one kind ('taxonomies' | 'places_queries' | 'professions') for the chosen tiers, in order, without repeats."""
    chosen = tiers or pack["tier_order"][:1]
    out = []
    for t in (pack["tier_order"] if chosen == ["all"] else chosen):
        for term in pack["tiers"][t].get(kind, []):
            if term not in out:
                out.append(term)
    return out
