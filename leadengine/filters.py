import json
import os
import re

DATA = os.path.join(os.path.dirname(__file__), "data")
SUFFIX = re.compile(r"\b(inc|llc|l\.l\.c|co|corp|corporation|company|ltd|the|dba)\b\.?", re.I)


def norm_name(name):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9& ]", " ", SUFFIX.sub(" ", name.lower()))).strip()


def load_blocklist(path=None):
    path = path or os.path.join(DATA, "enterprise_blocklist.txt")
    with open(path, encoding="utf-8") as fh:
        names = [ln.strip().lower() for ln in fh if ln.strip() and not ln.startswith("#")]
    return [re.compile(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])") for n in names]


def is_blocked(company, blocklist):
    low = company.lower()
    return any(p.search(low) for p in blocklist)


PUBLIC = re.compile(r"\b(authority|retirement system|county|city of|state of|department of|university|school district)\b", re.I)


def is_public_sector(company):
    return bool(PUBLIC.search(company))


HEALTH_SYSTEM = re.compile(r"\b(hospital|health system|healthcare system|university|medical group|urgent care|dialysis|davita|"
                           r"hackensack meridian|rwjbarnabas|atlanticare|virtua|inspira|atlantic health|valley health|"
                           r"englewood health|jefferson health|northwell|nyu langone|summit health|carepoint|"
                           r"cooper health|trinitas|saint barnabas|st\.? barnabas)\b", re.I)


def is_health_system(name):
    """Heuristic for 'not privately owned'. Ownership is not in NPPES; names are the only cheap signal."""
    return bool(HEALTH_SYSTEM.search(name))


def anonymous_employer(company):
    low = company.strip().lower()
    return not low or "@" in low or low in {"private", "confidential", "n/a", "undisclosed"}


class RoleRules:
    def __init__(self, professions=(), path=None):
        with open(path or os.path.join(DATA, "role_rules.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        inc = list(raw["include"]) + [re.escape(w) for p in professions for w in p.lower().split() if len(w) > 3]
        self.include = re.compile("|".join(inc), re.I)
        self.exclude = re.compile("|".join(raw["exclude"]), re.I)

    def relevant(self, title):
        return bool(self.include.search(title)) and not self.exclude.search(title)
