"""Pull FutureProofing campaign totals from Instantly and write data.json + history.json.

Totals only: no lead names, emails, companies or opens ever leave this script.
The key comes from the INSTANTLY_KEY environment variable (a GitHub Actions secret).
"""
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

API = "https://api.instantly.ai/api/v2/"
KEY = os.environ["INSTANTLY_KEY"]
HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = {0: "draft", 1: "live", 2: "paused", 3: "finished", 4: "error"}


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    for i in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (i + 1)); continue
            raise RuntimeError(f"{method} {path} -> {e.code}")


def pages(path, body=None):
    """All items from a paginated GET (body None) or POST list endpoint."""
    out, after = [], None
    while True:
        if body is None:
            d = call("GET", path + (f"&starting_after={after}" if after else ""))
        else:
            d = call("POST", path, {**body, **({"starting_after": after} if after else {})})
        out += d.get("items", [])
        after = d.get("next_starting_after")
        if not after or not d.get("items"):
            return out


def label(name):
    """'FP Client 2 Before They Hire (Jess)' -> ('client', 2, 'Before They Hire')."""
    m = re.match(r"FP (Client|Recruiting) (\d+) (.*?)(?: \((?:Jess|Gabe)\))?$", name)
    return (m.group(1).lower(), int(m.group(2)), m.group(3)) if m else None


def main():
    camps = [c for c in pages("campaigns?limit=100") if label(c["name"])]
    ids = [c["id"] for c in camps]
    stats = {a["campaign_id"]: a for a in call("GET", "campaigns/analytics?" + "&".join(f"ids={i}" for i in ids))}
    rows = []
    for c in camps:
        kind, num, name = label(c["name"])
        a = stats.get(c["id"], {})
        leads = pages("leads/list", {"campaign": c["id"], "limit": 100})
        replied = [l for l in leads if (l.get("email_reply_count") or 0) > 0]
        # Variant split of the first email, for A/B tests (empty when there is only one version)
        steps = call("GET", f"campaigns/analytics/steps?campaign_id={c['id']}")
        ab = [{"variant": "AB"[int(s["variant"])], "sent": s.get("sent") or 0, "replies": s.get("unique_replies") or 0}
              for s in (steps if isinstance(steps, list) else [])
              if str(s.get("step")) == "0" and s.get("variant") not in (None, "null")]
        rows.append({
            "kind": kind, "num": num, "name": name, "status": STATUS.get(c["status"], "other"),
            "leads": len(leads),
            "reached": sum(1 for l in leads if (l.get("timestamp_last_contact") or l.get("email_reply_count"))),
            "emails_sent": a.get("emails_sent_count") or 0,
            "replies": len(replied),
            "positive": sum(1 for l in replied if l.get("lt_interest_status") in (1, 2, 3)),
            "not_interested": sum(1 for l in replied if l.get("lt_interest_status") == -1),
            "bounced": a.get("bounced_count") or 0,
            "unsubscribed": a.get("unsubscribed_count") or 0,
            "ab": ab if len(ab) > 1 else [],
        })
    rows.sort(key=lambda r: (r["kind"] != "client", r["num"]))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = {k: sum(r[k] for r in rows if r["kind"] == "client")
             for k in ("leads", "reached", "emails_sent", "replies", "positive", "bounced", "unsubscribed")}
    json.dump({"updated": now, "total": total, "campaigns": rows}, open(os.path.join(HERE, "data.json"), "w"), indent=1)
    hp = os.path.join(HERE, "history.json")
    hist = json.load(open(hp)) if os.path.exists(hp) else []
    hist = [h for h in hist if h["date"] != now[:10]] + [{"date": now[:10], **total}]
    json.dump(hist, open(hp, "w"), indent=1)
    print(now, json.dumps(total))


if __name__ == "__main__":
    main()
