"""Geography registry. One file per state in data/geo/<ST>.json:

  {"state": "NJ", "counties": {"Middlesex": ["Edison", ...]}, "cities": ["Newark", ...]}

`counties` maps a county to its place names (used as NPPES / Places city filters); `cities` is the statewide sweep list.
Add a state by dropping a file in data/geo/ (see docs/ARCHITECTURE.md, 'Adding a geography'). Only NJ is loaded today, and only
Middlesex and Somerset counties are filled in."""
import json
import os

GEO_DIR = os.path.join(os.path.dirname(__file__), "data", "geo")


def available_states():
    return sorted(f[:-5] for f in os.listdir(GEO_DIR) if f.endswith(".json"))


def load_state(state):
    path = os.path.join(GEO_DIR, f"{state.upper()}.json")
    if not os.path.exists(path):
        raise SystemExit(f"No geography file for {state.upper()!r}. Loaded: {', '.join(available_states())}. "
                         "Add data/geo/<ST>.json (counties and cities); you can still target single cities with --city 'City, ST'.")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def county_cities(counties, state="NJ"):
    data = load_state(state)
    table = {k.lower(): v for k, v in data.get("counties", {}).items()}
    out, seen = [], set()
    for c in counties:
        if c.lower() not in table:
            raise SystemExit(f"County {c!r} is not loaded for {state.upper()}. Loaded: {', '.join(k.title() for k in table) or 'none'}. "
                             "Use --city 'City, ST' or add the county to data/geo/" + state.upper() + ".json.")
        for city in table[c.lower()]:
            if city not in seen:
                seen.add(city)
                out.append((city, state.upper()))
    return out


def statewide(state):
    data = load_state(state)
    cities = data.get("cities") or []
    if not cities:
        raise SystemExit(f"data/geo/{state.upper()}.json has no 'cities' list for a statewide sweep.")
    return [(c, state.upper()) for c in cities]


def resolve(geography):
    """geography: {"state": "NJ", "counties": [...], "cities": [...]} -> [(city, ST)]. Cities win, then counties, then the whole state."""
    state = (geography.get("state") or "").upper()
    if geography.get("cities"):
        out = []
        for c in geography["cities"]:
            city, _, st = c.rpartition(",")
            out.append((city.strip(), st.strip().upper()) if city else (c.strip(), state))
        return out
    if not state:
        raise SystemExit("geography needs a state, or a list of 'City, ST' entries")
    return county_cities(geography["counties"], state) if geography.get("counties") else statewide(state)
