"""Récupère en direct les annonces listées dans config/sources.yaml.

Sortie : data/listings.json (état courant), data/history.jsonl (changements),
data/REPORT.md (tableau lisible).
"""
import json, re, sys, time, datetime as dt
from pathlib import Path
import requests, yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; ecolodge-invest-bot/1.0; veille perso)"
PRICE_RE = re.compile(r"(\d{1,3}(?:[ \u00a0\u202f.]\d{3})+|\d{4,7})\s*(?:€|eur|euros|\$)", re.I)
SOLD_RE = re.compile(r"\b(vendu|sold|plus disponible|annonce expir[ée]e)\b", re.I)


def to_int(s: str) -> int:
    return int(re.sub(r"\D", "", s))


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def analyse(text: str, anchor: str, side: str = "after", window: int = 300) -> dict:
    """Prix + statut du bien repéré par `anchor`.

    side="after"  : le prix suit le titre (cas le plus courant)
    side="before" : le prix précède le titre (certaines pages Ceraolo)
    Le statut "vendu" n'est cherché qu'entre le titre et le prix (+ une marge côté
    "before" pour le badge), afin de ne pas attraper le bien voisin.
    Limite connue : un badge VENDU placé avant le titre d'un bien en mode "after" est raté.
    """
    idx = text.lower().find(anchor.lower())
    if idx == -1:
        return {"found": False, "price": None, "status": "introuvable"}
    a_end = idx + len(anchor)
    if side == "before":
        lo = max(0, idx - window)
        matches = list(PRICE_RE.finditer(text[lo:a_end]))
        m = matches[-1] if matches else None
        if m:
            p_start = lo + m.start()
            sold_zone = text[max(0, p_start - 120): a_end]
        else:
            sold_zone = text[max(0, idx - 120): a_end]
    else:
        zone = text[idx: idx + window]
        m = PRICE_RE.search(zone)
        sold_zone = zone[: m.end()] if m else zone[:120]
    price = None
    if m:
        v = to_int(m.group(1))
        if 20_000 <= v <= 10_000_000:
            price = v
    sold = bool(SOLD_RE.search(sold_zone))
    return {"found": True, "price": price, "status": "vendu/expiré" if sold else "actif"}


def fetch(url: str, retries: int = 2):
    err = "?"
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 200:
                return r.text, None
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            err = str(e)
        time.sleep(2 * (i + 1))
    return None, err


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config/sources.yaml").read_text())
    state_path = ROOT / "data/listings.json"
    old = json.loads(state_path.read_text()) if state_path.exists() else {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    new, changes, cache = {}, [], {}

    for s in cfg["sources"]:
        url = s["url"]
        if url not in cache:
            cache[url] = fetch(url)
            time.sleep(1.5)  # politesse
        html, err = cache[url]
        if html is None:
            prev = old.get(s["id"], {})
            new[s["id"]] = {**prev, "name": s["name"], "url": url,
                            "last_error": err, "checked_at": now}
            continue
        res = analyse(page_text(html), s["anchor"], s.get("price_side", "after"))
        res["expected_price"] = s.get("expected_price")
        rec = {"name": s["name"], "url": url, "units": s.get("units"),
               **res, "last_error": None, "checked_at": now}
        prev = old.get(s["id"])
        if prev and (prev.get("price") != rec["price"] or prev.get("status") != rec["status"]):
            changes.append({"id": s["id"], "at": now,
                            "from": {"price": prev.get("price"), "status": prev.get("status")},
                            "to": {"price": rec["price"], "status": rec["status"]}})
        new[s["id"]] = rec

    state_path.write_text(json.dumps(new, ensure_ascii=False, indent=2))
    if changes:
        with (ROOT / "data/history.jsonl").open("a") as f:
            for c in changes:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
    write_report(new, changes, now)
    print(f"{len(new)} sources, {len(changes)} changement(s)")
    return 0


def write_report(state: dict, changes: list, now: str) -> None:
    lines = [f"# Veille annonces — {now}", "",
             "| Bien | Prix (€) | Statut | Unités | Contrôle | Erreur |", "|---|---|---|---|---|---|"]
    for r in state.values():
        p = f"{r['price']:,}".replace(",", " ") if r.get("price") else "?"
        exp = r.get("expected_price")
        ctrl = "" if not exp else ("OK" if r.get("price") == exp else "à vérifier (prix ≠ référence)")
        lines.append(f"| [{r['name']}]({r['url']}) | {p} | {r.get('status','?')} | "
                     f"{r.get('units','')} | {ctrl} | {r.get('last_error') or ''} |")
    if changes:
        lines += ["", "## Changements depuis le dernier passage"]
        lines += [f"- **{c['id']}** : {c['from']} → {c['to']}" for c in changes]
    (ROOT / "data/REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
