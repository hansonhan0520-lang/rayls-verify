#!/usr/bin/env python3
"""Find the BRL1 proof-of-reserves documents linked from brl1.io and save them with a timestamp."""
import hashlib, json, os, re, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw", "por")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "rayls-verify-monitor"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.read()
found = {}
for page in ("https://fact.finance/en/reserves/brl1", "https://brl1.io", "https://brl1.io/en", "https://brl1.io/transparency", "https://brl1.io/en/transparency", "https://brl1.io/transparencia"):
    try:
        html = get(page).decode("utf-8", "replace")
    except Exception as e:
        print("page", page, "error", str(e)[:80]); continue
    print("page", page, len(html), "bytes")
    if "fact.finance" in page:
        open(os.path.join(OUT, "fact_finance_brl1.html"), "w").write(html)
        for m in re.findall(r'"(https?://[^"]*(?:api|reserve|por)[^"]*)"', html, re.I)[:40]:
            print("   api?", m[:200])
    for m in re.findall(r'https?://[^"\'\s<>\\]+', html):
        if re.search(r"\.pdf|reserv|transpar|attest|relat|audit|proof", m, re.I):
            found[m] = page
    for m in re.findall(r'href="(/[^"]+)"', html):
        if re.search(r"\.pdf|reserv|transpar|attest|relat|audit|proof", m, re.I):
            found[urllib.parse.urljoin(page, m)] = page
    for m in re.findall(r'[^<>"]{0,120}(?:Proof of Reserve|Prova de Reserva|reserve ratio|Relatório|attestation)[^<>"]{0,160}', html, re.I)[:20]:
        print("   text:", m.strip()[:280])
idx = []
for u in sorted(found):
    row = {"url": u, "seen_on": found[u]}
    if u.lower().split("?")[0].endswith(".pdf"):
        try:
            b = get(u)
            name = re.sub(r"[^A-Za-z0-9._-]", "_", urllib.parse.unquote(u.split("/")[-1].split("?")[0]))[-90:]
            open(os.path.join(OUT, name), "wb").write(b)
            row.update(file=name, bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
        except Exception as e:
            row["error"] = str(e)[:80]
    idx.append(row)
    print(json.dumps(row))
json.dump({"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "links": idx}, open(os.path.join(OUT, "index.json"), "w"), indent=1)
