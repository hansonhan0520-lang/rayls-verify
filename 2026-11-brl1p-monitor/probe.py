#!/usr/bin/env python3
"""One-off probe: which public endpoints answer the questions the monitor needs?
Read-only. Prints a short line per check."""
import json, time, urllib.request, urllib.error

UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}
LOCKBOX = "0x3Ea6BaC7d4138BcC126D0F17aE10122B3620abA6"
BRL1 = "0x5C067C80C00eCd2345b05E83A3e758eF799C40B5"
BRL1P = "0xA069d3798FEAb32994aC5D98A9F011DA6024f334"
ADAPTER = "0xE56dDf65E311CddB71f69c0aC4D27E58B239D69a"
OFT_SENT = "0x85496b760a4b7f8d66384b9df21b381f5d1b1e79f229a47aaf4c232edc2fe59a"
OFT_RECV = "0xefed6d3500546b29533b128a29e3a94d70788727f0507505ac12eaf2e578fd9c"


def http(url, body=None, tries=5):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(2 ** i); continue
            return e.code, e.read().decode()[:300]
        except Exception as e:
            if i < tries - 1:
                time.sleep(1); continue
            return -1, str(e)[:300]


def rpc(url, method, params):
    s, t = http(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    try:
        j = json.loads(t)
        return s, j.get("result"), j.get("error")
    except Exception:
        return s, None, t[:200]


def show(label, s, res, err=None):
    out = json.dumps(res)[:220] if res is not None else ""
    print(f"{label:58s} http={s} {'ERR ' + json.dumps(err)[:200] if err else out}", flush=True)


w = lambda a: a.lower()[2:].rjust(64, "0")
print("probe run", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

R = "https://mainnet-rpc.rayls.com"
s, head, e = rpc(R, "eth_blockNumber", []); show("rayls head", s, head, e)
for b in (12440000, 12500000, 12668378):
    s, r, e = rpc(R, "eth_call", [{"to": BRL1P, "data": "0x18160ddd"}, hex(b)])
    show(f"rayls totalSupply @ {b}", s, r, e)
for (a, b) in ((12437000, 12446999), (12660000, 12669999)):
    s, r, e = rpc(R, "eth_getLogs", [{"address": ADAPTER, "fromBlock": hex(a), "toBlock": hex(b)}])
    show(f"rayls getLogs adapter {a}-{b}", s, (len(r) if isinstance(r, list) else r), e)
if head:
    h = int(head, 16)
    s, r, e = rpc(R, "eth_getLogs", [{"address": ADAPTER, "fromBlock": hex(h - 50000), "toBlock": hex(h)}])
    show("rayls getLogs adapter last 50k", s, (len(r) if isinstance(r, list) else r), e)

s, t = http(f"https://explorer.rayls.com/api/v2/addresses/{ADAPTER}/logs")
try:
    j = json.loads(t); items = j.get("items", [])
    print(f"{'rayls explorer adapter logs page1':58s} http={s} items={len(items)} next={j.get('next_page_params')}")
    for it in items[:3]:
        print("   ", it.get("block_number"), it.get("transaction_hash"), it["topics"][0], (it.get("decoded") or {}).get("method_call"))
except Exception as ex:
    print("rayls explorer adapter logs", s, t[:200])

P = {"publicnode": "https://polygon-bor-rpc.publicnode.com", "drpc": "https://polygon.drpc.org",
     "polygon-rpc": "https://polygon-rpc.com", "llamarpc": "https://polygon.llamarpc.com",
     "1rpc": "https://1rpc.io/matic", "ankr": "https://rpc.ankr.com/polygon", "tenderly": "https://polygon.gateway.tenderly.co"}
for n, u in P.items():
    s, head_p, e = rpc(u, "eth_blockNumber", []); show(f"polygon {n} head", s, head_p, e)
    s, r, e = rpc(u, "eth_call", [{"to": BRL1, "data": "0x70a08231" + w(LOCKBOX)}, hex(95500000)])
    show(f"polygon {n} balanceOf @95500000", s, r, e)
    s, r, e = rpc(u, "eth_getLogs", [{"address": LOCKBOX, "fromBlock": hex(95472945), "toBlock": hex(95472945 + 9999)}])
    show(f"polygon {n} getLogs lockbox 10k", s, (len(r) if isinstance(r, list) else r), e)

s, t = http(f"https://polygon.blockscout.com/api/v2/addresses/{LOCKBOX}/logs")
first_tx = None
try:
    j = json.loads(t); items = j.get("items", [])
    print(f"{'polygon blockscout lockbox logs page1':58s} http={s} items={len(items)} next={j.get('next_page_params')}")
    for it in items[:3]:
        print("   ", it.get("block_number"), it.get("transaction_hash"), it["topics"][0])
        if it["topics"][0] == OFT_SENT and not first_tx:
            first_tx = it["transaction_hash"]
    first_tx = first_tx or (items[0]["transaction_hash"] if items else None)
except Exception:
    print("polygon blockscout lockbox logs", s, t[:200])

for base in ("https://scan.layerzero-api.com/v1", "https://scan-testnet.layerzero-api.com/v1"):
    if first_tx:
        s, t = http(f"{base}/messages/tx/{first_tx}")
        print(f"{'layerzero scan ' + base.split('//')[1][:22] + ' tx':58s} http={s} {t[:400]}")
s, t = http(f"https://scan.layerzero-api.com/v1/messages/oapp/30109/{LOCKBOX}")
print(f"{'layerzero scan by oapp':58s} http={s} {t[:400]}")
s, t = http("https://metadata.layerzero-api.com/v1/metadata/dvns")
print(f"{'layerzero dvn metadata':58s} http={s} bytes={len(t)}")
for u in ("https://brl1.io", "https://www.brl1.io", "https://dapp.rayls.com"):
    s, t = http(u)
    print(f"{'web ' + u:58s} http={s} bytes={len(t)}")
print("probe done", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
