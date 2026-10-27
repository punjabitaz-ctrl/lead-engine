"""Vertical packs: what to look for in a market. One JSON file per pack in data/verticals/.

  id, label, industry     naming and the industry label used for scoring/fit
  sources                 default discovery sources (nppes | places | adzuna | csv | manual)
  tier_order, tiers       ordered groups of search terms: taxonomies (NPPES), places_queries (Google Places), professions (job boards)

Optional, so one engine serves any market without code changes:
  config                  overrides of config.DEFAULTS for this market (size basis and thresholds, points, target employees)
  role_rules              {"include": [...], "exclude": [...]} regexes deciding which job titles count as the signal
  ownership_exclude       regexes for names that are not independent buyers (chains, franchises, health systems)
  templates               email template set in data/templates/ (default: data/templates.json)
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


def role_rules(pack):
    """The pack's own posting rules ({"include": [...], "exclude": [...]}), or None for the default website-project rules."""
    return (pack or {}).get("role_rules")


def ownership_patterns(pack):
    """Regexes for names that are not independent buyers in this market (chains, franchises, systems). Matched case-insensitively."""
    import re
    return [re.compile(p, re.I) for p in (pack or {}).get("ownership_exclude", [])]


def templates(pack):
    """Email template set for the pack: a file name in data/templates/, or None for the default data/templates.json."""
    name = (pack or {}).get("templates")
    if not name:
        return None
    path = os.path.join(os.path.dirname(DIR), "templates", name if name.endswith(".json") else name + ".json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
