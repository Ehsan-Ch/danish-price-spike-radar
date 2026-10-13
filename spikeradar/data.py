"""Official quarter-hour prices, normalized without filling missing observations."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "https://api.energidataservice.dk/"
AREAS = ("DK1", "DK2")

def stamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def download(folder, start="2025-10-01", end="2026-10-01"):
    if start < "2025-10-01" or stamp(start) >= stamp(end):
        raise ValueError("Use local dates from 2025-10-01, with end after start")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    url = BASE + "dataset/DayAheadPrices?" + urlencode({
        "start": start, "end": end, "filter": json.dumps({"PriceArea": list(AREAS)}),
        "sort": "TimeUTC,PriceArea", "columns": "TimeUTC,PriceArea,DayAheadPriceEUR", "limit": 0})
    with urlopen(url, timeout=120) as response:
        raw = response.read()
    payload = json.loads(raw)
    if not payload.get("records") or payload.get("total", len(payload["records"])) != len(payload["records"]):
        raise ValueError("Empty or truncated API response")
    with urlopen(BASE + "meta/dataset/DayAheadPrices", timeout=30) as response:
        metadata = json.load(response)
    manifest = {"dataset": "DayAheadPrices", "source_url": url,
        "start_local_inclusive": start, "end_local_exclusive": end,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(), "records": len(payload["records"]),
        "metadata": metadata}
    (folder / "prices.json").write_bytes(raw)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

def normalize(payload):
    groups, seen = defaultdict(list), set()
    invalid = 0
    for row in payload["records"]:
        area = row["PriceArea"]
        if area not in AREAS:
            continue
        t = stamp(row["TimeUTC"])
        if (area, t) in seen:
            raise ValueError("Duplicate price interval")
        seen.add((area, t))
        if t.minute not in (0, 15, 30, 45) or t.second or t.microsecond:
            raise ValueError("Expected aligned quarter-hour prices")
        key = (area, t.replace(minute=0))
        groups[key]
        v = row["DayAheadPriceEUR"]
        if v is None or not math.isfinite(float(v)):
            invalid += 1
            continue
        groups[key].append(float(v))
    series = {a: {} for a in AREAS}
    incomplete = 0
    for (a, t), values in groups.items():
        if len(values) == 4:
            series[a][t] = sum(values) / 4
        else:
            incomplete += 1
    missing = {}
    for area, data in series.items():
        times = sorted(data)
        missing[area] = sum(int((b-a).total_seconds()/3600)-1 for a,b in zip(times,times[1:]))
    return series, {"invalid_quarters": invalid, "incomplete_hours": incomplete,
                    "missing_hours_between_endpoints": missing,
                    "complete_hours": {a: len(s) for a,s in series.items()}}

def load(folder):
    folder = Path(folder)
    raw = (folder / "prices.json").read_bytes()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise ValueError("Cached data hash does not match manifest")
    series, quality = normalize(json.loads(raw))
    return series, quality, manifest

