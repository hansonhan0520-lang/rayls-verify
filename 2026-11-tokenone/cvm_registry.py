#!/usr/bin/env python3
"""Read TokenOne's current entry in Brazil's official CVM public registries.

Read-only, standard library only. This checks the platform's registration, not the merits
or registration status of every offering. TokenOne's own FAQ says its CVM Resolution 88
offerings use a registration exemption and are not reviewed individually by CVM in advance.

Output: data/cvm.json and raw/cvm/tokenone_registry.json
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.environ.get("RAYLS_AUDIT_OUT", HERE)
BASE = "https://web.cvm.gov.br/app/crowdfunding-web/"
ENDPOINT = BASE + "consultarRegistro/getRegistrosCrowdfunding"
HEADERS = {
    "User-Agent": "rayls-verify-research",
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": BASE,
}
PAYLOAD = {
    "filtroRegistroBean": {"denominacaoSocial": {"nome": "TOKENONE"}},
    "filtroSituacaoCrowdfunding": [],
}


def request(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def main():
    # Establish the same public session a browser would use before querying the registry.
    request(BASE)
    raw = request(ENDPOINT, PAYLOAD)
    entries = json.loads(raw.decode())
    checked = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    result = {
        "checked_utc": checked,
        "source": BASE + "#/consultaPublica",
        "endpoint": ENDPOINT,
        "filter": PAYLOAD,
        "entries": entries,
        "note": "Platform registration only. It is not a CVM review of NF01, NF02 or NF03.",
    }
    os.makedirs(os.path.join(OUT_ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(OUT_ROOT, "raw", "cvm"), exist_ok=True)
    with open(os.path.join(OUT_ROOT, "data", "cvm.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_ROOT, "raw", "cvm", "tokenone_registry.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
