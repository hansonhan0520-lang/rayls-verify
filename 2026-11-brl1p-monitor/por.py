#!/usr/bin/env python3
"""Save the pages that describe BRL1's reserves, and any PoR documents they link, with a timestamp.
Output: raw/por/<name>.html (or .pdf) and raw/por/index.json"""
import hashlib, json, os, re, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw", "por")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (rayls-verify-monitor)"}
PAGES = ["https://brl1.io/en", "https://brl1.io/en/como_funciona", "https://fact.finance/en/reserves/brl1",
         "https://fact.finance/en/reserves/brl1?frame=true", "https://docs.fact.finance/features/por/",
         "https://docs.fact.finance/cases/stablecoins/"]
KEY = re.compile(r"\.pdf|reserv|transpar|attest|relat|audit|proof|drive\.google", re.I)
idx = {"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": [], "links": {}}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.status, r.geturl(), r.read()
for page in PAGES:
    try:
        st, final, b = get(page)
    except Exception as e:
        idx["pages"].append({"url": page, "error": str(e)[:150]}); print(page, "ERROR", e); continue
    name = re.sub(r"[^A-Za-z0-9]+", "_", page.split("//")[1])[:80] + ".html"
    open(os.path.join(OUT, name), "wb").write(b)
    idx["pages"].append({"url": page, "final_url": final, "status": st, "file": name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    html = b.decode("utf-8", "replace")
    for m in re.findall(r'https?://[^"\'\s<>\\)]+', html) + [urllib.parse.urljoin(page, h) for h in re.findall(r'href="(/[^"]+)"', html)]:
        if KEY.search(m) and "fonts" not in m and ".css" not in m:
            idx["links"].setdefault(m, page)
    print(page, st, len(b))
for u in list(idx["links"]):
    if u.lower().split("?")[0].endswith(".pdf"):
        try:
            st, final, b = get(u)
            name = re.sub(r"[^A-Za-z0-9._-]", "_", urllib.parse.unquote(u.split("/")[-1].split("?")[0]))[-90:]
            open(os.path.join(OUT, name), "wb").write(b)
            idx["links"][u] = {"seen_on": idx["links"][u], "file": name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        except Exception as e:
            idx["links"][u] = {"seen_on": idx["links"][u], "error": str(e)[:100]}
json.dump(idx, open(os.path.join(OUT, "index.json"), "w"), indent=1)
