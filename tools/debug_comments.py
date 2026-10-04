"""Диагностика: что Threads API отдаёт по нашим последним постам."""
import json, os, requests
from autopost import API, load_posts
tok = os.environ["THREADS_ACCESS_TOKEN"]
r = requests.get(f"{API}/me/threads", params={"fields": "id,text,timestamp", "limit": 25, "access_token": tok}, timeout=30)
print("me/threads:", r.status_code)
known = {p.get("threads_id") for p in load_posts()}
for t in r.json().get("data", []):
    tid = t["id"]
    ins = requests.get(f"{API}/{tid}/insights", params={"metric": "replies", "access_token": tok}, timeout=30).json()
    reps = [d.get("values", [{}])[0].get("value", d.get("total_value", {}).get("value")) for d in ins.get("data", [])]
    conv = requests.get(f"{API}/{tid}/conversation", params={"fields": "id,username,text,timestamp,hide_status", "access_token": tok}, timeout=30).json()
    rp = requests.get(f"{API}/{tid}/replies", params={"fields": "id,username,text,hide_status", "access_token": tok}, timeout=30).json()
    print(f"\n== {tid} known={tid in known} {t['timestamp']} insights_replies={reps} | {t.get('text','')[:50]!r}")
    for c in conv.get("data", []):
        print("  conv:", c.get("id"), c.get("username"), c.get("hide_status"), repr(c.get("text", "")[:80]))
    if "error" in conv: print("  conv error:", conv["error"])
    print("  replies:", len(rp.get("data", [])), rp.get("error"))
