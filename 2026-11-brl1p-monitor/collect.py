#!/usr/bin/env python3
"""BRL1.p backing monitor: rebuild the whole history of the bridge, record by record.

Read-only. Standard library only. Sends eth_call / eth_getLogs / eth_getBlockByNumber
to public RPC endpoints and GET requests to two public explorer-style APIs.

What it produces (in this folder):
  data/transfers.csv      one row per bridge transfer, both chains, with transaction
                          hashes and the LayerZero message GUID read from each side
  data/timeline.csv       every change to the lockbox balance and to BRL1.p supply,
                          merged by time, with the running totals after each change
  data/polygon_daily.csv  Polygon-side state read at 00:00 UTC on every day since the
                          lockbox was created (archive reads, two independent providers)
  data/config_events.csv  every admin/config event found for the contracts involved
  data/live.json          current state of both sides at the time of the run
  data/summary.json       the numbers the article quotes
  raw/                    raw responses the tables were built from
  runs/<time>.txt         human-readable log of this run

Why events instead of historical reads on Rayls: on 6 Nov 2026 the official Rayls RPC
answered every historical eth_call with "state at block ... is pruned", so past BRL1.p
supply cannot be read back from it; it has to be rebuilt from mint and burn events.
"""
import csv, json, os, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "rayls-verify-monitor", "Content-Type": "application/json"}

POLY = {"publicnode": ("https://polygon-bor-rpc.publicnode.com", 5000),
        "tenderly": ("https://polygon.gateway.tenderly.co", 10000)}
POLY_ARCHIVE = {"drpc": "https://polygon.drpc.org", "tenderly": "https://polygon.gateway.tenderly.co"}
RAYLS_RPC = "https://mainnet-rpc.rayls.com"
RAYLS_API = "https://explorer.rayls.com/api/v2"
LZ_SCAN = "https://scan.layerzero-api.com/v1"

BRL1 = "0x5c067c80c00ecd2345b05e83a3e758ef799c40b5"
LOCKBOX = "0x3ea6bac7d4138bcc126d0f17ae10122b3620aba6"
BRL1P = "0xa069d3798feab32994ac5d98a9f011da6024f334"
ADAPTER = "0xe56ddf65e311cddb71f69c0ac4d27e58b239d69a"
EP_POLYGON = "0x1a44076050125825900e736c501f859c50fe728c"
EID_POLYGON, EID_RAYLS = 30109, 30415
LOCKBOX_FROM = 95472945
RAYLS_FROM = 12430000

T = {  # event topics (keccak256 of the signature)
    "Transfer": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
    "OFTSent": "0x85496b760a4b7f8d66384b9df21b381f5d1b1e79f229a47aaf4c232edc2fe59a",
    "OFTReceived": "0xefed6d3500546b29533b128a29e3a94d70788727f0507505ac12eaf2e578fd9c",
    "OwnershipTransferred": "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0",
    "RoleGranted": "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d",
    "RoleRevoked": "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b",
    "Upgraded": "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b",
    "Paused": "0x62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a258",
    "Unpaused": "0x5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa",
    "PeerSet": "0x238399d427b947898edb290f5ff0f9109849b1c3ba196a42e35f00c50a54b98b",
    "DelegateSet": "0x6ee10e9ed4d6ce9742703a498707862f4b00f1396a87195eb93267b3d7983981",
    "UlnConfigSet": "0x82118522aa536ac0e96cc5c689407ae42b89d592aa133890a01f1509842f5081",
    "ExecutorConfigSet": "0x779cb2dd9d2bb1be1737d05435d744facbfb84a2a4912e21379d39beddcdc805",
    "ReceiveLibrarySet": "0xcd6f92f5ac6185a5acfa02c92090746cec64d777269cbcd0ed031e396657a1c2",
    "SendLibrarySet": "0x4cff966ebee29a156dcb34cf72c1d06231fb1777f6bdf6e8089819232f002b1c",
}
NAME = {v: k for k, v in T.items()}
ROLE = {"DEFAULT_ADMIN": "0" * 64,
        "MINTER": "9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6",
        "BURNER": "3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a848",
        "PAUSER": "65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a",
        "UPGRADER": "189ab7a9244df0848122154315af71fe140f3db0fe014031783b0946b8c9d2e3"}
ADMIN = "0x633ac5e2315b973417e8caa6b3ad2162e0461ce1"
SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
Z64 = "0x" + "0" * 64

LOG = []


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http(url, body=None, tries=7):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.read().decode()[:200]}"
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last)
        except Exception as e:
            last = str(e)
        time.sleep(min(30, 1.5 * 2 ** i))
    raise RuntimeError(f"{url}: {last}")


def rpc(url, method, params):
    for i in range(5):
        j = http(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" not in j and j.get("result") is not None:
            return j["result"]
        err = j.get("error")
        if err and ("pruned" in str(err) or "not available" in str(err) or "execution reverted" in str(err)):
            raise RuntimeError(str(err))
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{method} on {url}: {j.get('error') or 'null result'}")


w = lambda a: a.lower().replace("0x", "").rjust(64, "0")
u32 = lambda n: format(n, "064x")
addr = lambda word: "0x" + word[-40:].lower()
fmt = lambda wei: f"{wei / 10**18:,.6f}"


def call(url, to, data, block="latest"):
    return rpc(url, "eth_call", [{"to": to, "data": data}, block if isinstance(block, str) else hex(block)])


def decode_uln(h):
    words = [h[2 + i:2 + i + 64] for i in range(0, len(h) - 2, 64)]
    t = words[3:]
    conf, req, opt = int(t[0], 16), int(t[1], 16), int(t[2], 16)
    rs = int(t[4], 16) // 32
    os_ = int(t[5], 16) // 32
    dvns = [addr(t[rs + 1 + i]) for i in range(int(t[rs], 16))]
    odvns = [addr(t[os_ + 1 + i]) for i in range(int(t[os_], 16))]
    return {"confirmations": conf, "required": req, "optional": opt, "threshold": int(t[3], 16),
            "dvns": sorted(dvns), "optional_dvns": sorted(odvns)}


# ---------------------------------------------------------------- Polygon logs
def poly_logs(name, head, out):
    url, step = POLY[name]
    res = {"in": [], "out": [], "lockbox": []}
    queries = {"in": {"address": BRL1, "topics": [T["Transfer"], None, "0x" + w(LOCKBOX)]},
               "out": {"address": BRL1, "topics": [T["Transfer"], "0x" + w(LOCKBOX)]},
               "lockbox": {"address": LOCKBOX}}
    calls = 0
    for b in range(LOCKBOX_FROM, head + 1, step):
        e = min(b + step - 1, head)
        for k, q in queries.items():
            res[k] += rpc(url, "eth_getLogs", [dict(q, fromBlock=hex(b), toBlock=hex(e))])
            calls += 1
    out[name] = res
    out[name + "_calls"] = calls


def block_ts(url, n, cache):
    if n not in cache:
        cache[n] = int(rpc(url, "eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
    return cache[n]


def block_at(url, ts, lo, hi, cache):
    """Last block with timestamp <= ts (binary search)."""
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if block_ts(url, mid, cache) <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


# ---------------------------------------------------------------- Rayls explorer
def explorer_logs(address):
    out, nxt, pages = [], None, 0
    while True:
        q = ("?" + urllib.parse.urlencode(nxt)) if nxt else ""
        j = http(f"{RAYLS_API}/addresses/{address}/logs{q}")
        out += j.get("items", [])
        nxt = j.get("next_page_params")
        pages += 1
        if not nxt or pages > 200:
            return out


CHECKSUM = {LOCKBOX: "0x3Ea6BaC7d4138BcC126D0F17aE10122B3620abA6", ADAPTER: "0xE56dDf65E311CddB71f69c0aC4D27E58B239D69a"}


def lz_messages(eid, oapp):
    """LayerZero Scan, an index run by LayerZero Labs. It answered only for checksummed addresses."""
    out, token, pages = [], None, 0
    while True:
        q = (f"?nextToken={urllib.parse.quote(token)}" if token else "")
        try:
            j = http(f"{LZ_SCAN}/messages/oapp/{eid}/{CHECKSUM[oapp]}{q}")
        except Exception as e:
            log(f"    LayerZero Scan {eid}/{oapp}: {str(e)[:120]}")
            return out
        out += j.get("data", [])
        token = j.get("nextToken")
        pages += 1
        if not token or pages > 50:
            return out


def main():
    started = time.time()
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for d in ("data", "raw", "runs"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    log(f"BRL1.p backing monitor, run started {utc(started)}")

    # ---- heads
    p_url = POLY["tenderly"][0]
    p_head = int(rpc(p_url, "eth_blockNumber", []), 16) - 10
    r_head = int(rpc(RAYLS_RPC, "eth_blockNumber", []), 16) - 10
    pcache, rcache = {}, {}
    log(f"Polygon head used {p_head} ({utc(block_ts(p_url, p_head, pcache))}); Rayls head used {r_head}")

    # ---- Polygon logs from two providers in parallel
    pl = {}
    ths = [threading.Thread(target=poly_logs, args=(n, p_head, pl)) for n in POLY]
    [t.start() for t in ths]

    # ---- Rayls side while Polygon runs
    rl_token = explorer_logs(BRL1P)
    rl_adapter = explorer_logs(ADAPTER)
    log(f"Rayls explorer: {len(rl_token)} BRL1.p logs, {len(rl_adapter)} adapter logs")
    # Rayls RPC eth_getLogs over the same span, to see whether the RPC alone could rebuild history
    rpc_counts = {"token": 0, "adapter": 0, "errors": 0}
    for b in range(RAYLS_FROM, r_head + 1, 50000):
        for k, a in (("token", BRL1P), ("adapter", ADAPTER)):
            try:
                rpc_counts[k] += len(rpc(RAYLS_RPC, "eth_getLogs", [{"address": a, "fromBlock": hex(b), "toBlock": hex(min(b + 49999, r_head))}]))
            except Exception:
                rpc_counts["errors"] += 1
    log(f"Rayls RPC eth_getLogs over the same blocks: {rpc_counts}")
    lz = {"polygon_to_rayls": lz_messages(EID_POLYGON, LOCKBOX), "rayls_to_polygon": lz_messages(EID_RAYLS, ADAPTER)}
    log(f"LayerZero Scan: {len(lz['polygon_to_rayls'])} messages Polygon->Rayls, {len(lz['rayls_to_polygon'])} Rayls->Polygon")
    [t.join() for t in ths]
    for n in POLY:
        log(f"Polygon {n}: {len(pl[n]['in'])} transfers in, {len(pl[n]['out'])} out, {len(pl[n]['lockbox'])} lockbox logs, {pl[n + '_calls']} calls")
    key = lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16))
    same = all(sorted((l["transactionHash"], l["logIndex"], l["data"]) for l in pl["publicnode"][k]) ==
               sorted((l["transactionHash"], l["logIndex"], l["data"]) for l in pl["tenderly"][k]) for k in ("in", "out", "lockbox"))
    log(f"Polygon providers agree log for log: {same}")
    P = pl["tenderly"]
    for k in P:
        P[k].sort(key=key)

    json.dump({"polygon": P, "rayls_brl1p": rl_token, "rayls_adapter": rl_adapter, "layerzero_scan": lz},
              open(os.path.join(HERE, "raw", "logs.json"), "w"))

    # ---- decode Polygon side
    poly_tx = {}
    for l in P["lockbox"]:
        tx = l["transactionHash"]
        d = poly_tx.setdefault(tx, {"block": int(l["blockNumber"], 16)})
        nm = NAME.get(l["topics"][0], l["topics"][0])
        if nm == "OFTSent":
            d.update(dir="P->R", guid=l["topics"][1], user=addr(l["topics"][2]),
                     eid=int(l["data"][2:66], 16), sent=int(l["data"][66:130], 16), recv=int(l["data"][130:194], 16))
        elif nm == "OFTReceived":
            d.update(dir="R->P", guid=l["topics"][1], user=addr(l["topics"][2]),
                     eid=int(l["data"][2:66], 16), recv=int(l["data"][66:130], 16))
    for k, sign in (("in", 1), ("out", -1)):
        for l in P[k]:
            d = poly_tx.setdefault(l["transactionHash"], {"block": int(l["blockNumber"], 16)})
            d.setdefault("lockbox_delta", 0)
            d["lockbox_delta"] += sign * int(l["data"], 16)

    # ---- decode Rayls side
    ray_tx = {}
    for l in rl_adapter + rl_token:
        tx = l["transaction_hash"]
        d = ray_tx.setdefault(tx, {"block": l["block_number"]})
        nm = NAME.get(l["topics"][0], l["topics"][0])
        data = l["data"]
        if l["address"]["hash"].lower() == ADAPTER and nm == "OFTSent":
            d.update(dir="R->P", guid=l["topics"][1], user=addr(l["topics"][2]),
                     eid=int(data[2:66], 16), sent=int(data[66:130], 16), recv=int(data[130:194], 16))
        elif l["address"]["hash"].lower() == ADAPTER and nm == "OFTReceived":
            d.update(dir="P->R", guid=l["topics"][1], user=addr(l["topics"][2]),
                     eid=int(data[2:66], 16), recv=int(data[66:130], 16))
        elif l["address"]["hash"].lower() == BRL1P and nm == "Transfer":
            if l["topics"][1] == Z64:
                d["supply_delta"] = d.get("supply_delta", 0) + int(data, 16)
            elif l["topics"][2] == Z64:
                d["supply_delta"] = d.get("supply_delta", 0) - int(data, 16)
    for d in list(poly_tx.values()) + list(ray_tx.values()):
        pass
    for tx, d in ray_tx.items():
        if "supply_delta" in d or "guid" in d:
            d["ts"] = block_ts(RAYLS_RPC, d["block"], rcache)
    for tx, d in poly_tx.items():
        d["ts"] = block_ts(p_url, d["block"], pcache)

    # ---- LayerZero Scan index by GUID
    lzg = {}
    for direction, msgs in lz.items():
        for m in msgs:
            g = (m.get("guid") or "").lower()
            lzg[g] = {"status": (m.get("status") or {}).get("name"),
                      "src_tx": ((m.get("source") or {}).get("tx") or {}).get("txHash", "").lower(),
                      "dst_tx": ((m.get("destination") or {}).get("tx") or {}).get("txHash", "").lower(),
                      "nonce": (m.get("pathway") or {}).get("nonce")}

    # ---- pair by GUID
    rows, problems = [], []
    p_by_g = {d["guid"].lower(): (tx, d) for tx, d in poly_tx.items() if "guid" in d}
    r_by_g = {d["guid"].lower(): (tx, d) for tx, d in ray_tx.items() if "guid" in d}
    for g in sorted(set(p_by_g) | set(r_by_g), key=lambda g: min([x[1]["ts"] for x in (p_by_g.get(g), r_by_g.get(g)) if x])):
        ptx, pd = p_by_g.get(g, (None, {}))
        rtx, rd = r_by_g.get(g, (None, {}))
        direction = pd.get("dir") or rd.get("dir")
        lzm = lzg.get(g, {})
        if direction == "P->R":
            src, dst, amt_src, amt_dst = (ptx, pd), (rtx, rd), pd.get("lockbox_delta"), rd.get("supply_delta")
        else:
            src, dst, amt_src, amt_dst = (rtx, rd), (ptx, pd), -(rd.get("supply_delta") or 0), -(pd.get("lockbox_delta") or 0)
        ok = (src[0] and dst[0] and amt_src == amt_dst and lzm.get("src_tx") == (src[0] or "").lower()
              and lzm.get("dst_tx") == (dst[0] or "").lower())
        row = {"direction": direction, "guid": g, "nonce": lzm.get("nonce"),
               "src_tx": src[0], "src_block": src[1].get("block"), "src_time": utc(src[1]["ts"]) if src[0] else "",
               "dst_tx": dst[0], "dst_block": dst[1].get("block"), "dst_time": utc(dst[1]["ts"]) if dst[0] else "",
               "amount_locked_or_burned": fmt(amt_src or 0), "amount_minted_or_unlocked": fmt(amt_dst or 0),
               "latency_s": (dst[1]["ts"] - src[1]["ts"]) if (src[0] and dst[0]) else "",
               "user": pd.get("user") or rd.get("user"), "layerzero_status": lzm.get("status"),
               "layerzero_scan_matches_chain": bool(lzm) and lzm.get("src_tx") == (src[0] or "").lower() and lzm.get("dst_tx") == (dst[0] or "").lower(),
               "all_checks_pass": bool(ok)}
        rows.append(row)
        if not ok:
            problems.append(row)
    # balance changes with no bridge message behind them
    stray_p = [(tx, d) for tx, d in poly_tx.items() if d.get("lockbox_delta") and "guid" not in d]
    stray_r = [(tx, d) for tx, d in ray_tx.items() if d.get("supply_delta") and "guid" not in d]
    lz_only = [g for g in lzg if g not in p_by_g and g not in r_by_g]
    with open(os.path.join(HERE, "data", "transfers.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["none"])
        cw.writeheader()
        cw.writerows(rows)
    n_pr = sum(r["direction"] == "P->R" for r in rows)
    n_rp = sum(r["direction"] == "R->P" for r in rows)
    log(f"\n[1] Transfers paired by LayerZero GUID: {len(rows)} ({n_pr} Polygon->Rayls, {n_rp} Rayls->Polygon)")
    log(f"    all checks pass: {len(rows) - len(problems)} of {len(rows)}")
    log(f"    lockbox balance changes with no bridge message: {len(stray_p)}  {[tx for tx, _ in stray_p]}")
    log(f"    BRL1.p supply changes with no bridge message:  {len(stray_r)}  {[tx for tx, _ in stray_r]}")
    log(f"    LayerZero Scan messages not found on either chain: {len(lz_only)}")
    lats = sorted(r["latency_s"] for r in rows if r["direction"] == "P->R" and r["latency_s"] != "")
    latr = sorted(r["latency_s"] for r in rows if r["direction"] == "R->P" and r["latency_s"] != "")
    if lats:
        log(f"    Polygon->Rayls latency min/median/max s: {lats[0]}/{lats[len(lats)//2]}/{lats[-1]}")
    if latr:
        log(f"    Rayls->Polygon latency s: {latr}")

    # ---- timeline: every change on either side, merged by time
    ev = [(d["ts"], 0, d["block"], tx, "polygon", d["lockbox_delta"], 0) for tx, d in poly_tx.items() if d.get("lockbox_delta")]
    ev += [(d["ts"], 1, d["block"], tx, "rayls", 0, d["supply_delta"]) for tx, d in ray_tx.items() if d.get("supply_delta")]
    ev.sort()
    lockbox = supply = 0
    worst = None
    tl = []
    for ts, _, blk, tx, chain, dl, ds in ev:
        lockbox += dl
        supply += ds
        gap = lockbox - supply
        if worst is None or gap < worst[0]:
            worst = (gap, utc(ts), tx)
        tl.append({"time": utc(ts), "chain": chain, "block": blk, "tx": tx, "lockbox_change": fmt(dl), "supply_change": fmt(ds),
                   "lockbox_after": fmt(lockbox), "supply_after": fmt(supply), "lockbox_minus_supply": fmt(gap)})
    with open(os.path.join(HERE, "data", "timeline.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(tl[0].keys()))
        cw.writeheader()
        cw.writerows(tl)
    log(f"\n[2] Timeline: {len(tl)} balance changes merged by time")
    log(f"    smallest lockbox - supply at any point: {fmt(worst[0])} at {worst[1]} ({worst[2]})")
    log(f"    supply ever above lockbox: {worst[0] < 0}")
    log(f"    rebuilt from events now: lockbox {fmt(lockbox)}, supply {fmt(supply)}")

    # ---- check the rebuilt Polygon balance against archive reads at every change
    arch = {}
    for n, url in POLY_ARCHIVE.items():
        bad = checked = 0
        for row in tl:
            if row["chain"] != "polygon":
                continue
            try:
                v = int(call(url, BRL1, "0x70a08231" + w(LOCKBOX), row["block"]), 16)
                checked += 1
                bad += fmt(v) != row["lockbox_after"]
            except Exception as e:
                arch.setdefault(n + "_errors", []).append(str(e)[:80])
        arch[n] = {"checked": checked, "mismatched": bad}
    log(f"    Polygon archive balanceOf at each change matches the rebuilt balance: {arch}")

    # ---- live state, both sides
    live = {"polygon_block": p_head, "rayls_block": r_head}
    live["lockbox_brl1"] = int(call(p_url, BRL1, "0x70a08231" + w(LOCKBOX), p_head), 16)
    live["lockbox_brl1_publicnode"] = int(call(POLY["publicnode"][0], BRL1, "0x70a08231" + w(LOCKBOX)), 16)
    live["brl1p_supply"] = int(call(RAYLS_RPC, BRL1P, "0x18160ddd", r_head), 16)
    try:
        live["brl1p_supply_explorer"] = int(http(f"{RAYLS_API}/tokens/{BRL1P}")["total_supply"])
    except Exception as e:
        live["brl1p_supply_explorer"] = str(e)[:80]
    live["roles"] = {}
    for who in (ADMIN, ADAPTER):
        live["roles"][who] = [k for k, v in ROLE.items() if int(call(RAYLS_RPC, BRL1P, "0x91d14854" + v + w(who)), 16) == 1]
    live["brl1p_impl"] = addr(rpc(RAYLS_RPC, "eth_getStorageAt", [BRL1P, SLOT_IMPL, "latest"]))
    live["adapter_owner"] = addr(call(RAYLS_RPC, ADAPTER, "0x8da5cb5b"))
    live["adapter_peer"] = addr(call(RAYLS_RPC, ADAPTER, "0xbb0b6a53" + u32(EID_POLYGON)))
    ep_r = addr(call(RAYLS_RPC, ADAPTER, "0x5e280f11"))
    live["rayls_endpoint"] = ep_r
    live["adapter_delegate"] = addr(call(RAYLS_RPC, ep_r, "0x587cde1e" + w(ADAPTER)))
    rlib = addr(call(RAYLS_RPC, ep_r, "0x402f8468" + w(ADAPTER) + u32(EID_POLYGON))[:66])
    slib = addr(call(RAYLS_RPC, ep_r, "0xb96a277f" + w(ADAPTER) + u32(EID_POLYGON)))
    live["rayls_receive_uln"] = decode_uln(call(RAYLS_RPC, ep_r, "0x2b3197b9" + w(ADAPTER) + w(rlib) + u32(EID_POLYGON) + u32(2)))
    live["rayls_send_uln"] = decode_uln(call(RAYLS_RPC, ep_r, "0x2b3197b9" + w(ADAPTER) + w(slib) + u32(EID_POLYGON) + u32(2)))
    live["rayls_libs"] = {"receive": rlib, "send": slib}
    live["brl1p_paused"] = None
    try:
        live["brl1p_paused"] = int(call(RAYLS_RPC, BRL1P, "0x5c975abb"), 16) == 1
    except Exception:
        pass
    try:
        meta = http("https://metadata.layerzero-api.com/v1/metadata/dvns")
        names = {}
        for chain in ("rayls", "polygon"):
            for a, v in ((meta.get(chain) or {}).get("dvns") or {}).items():
                names[f"{chain}:{a.lower()}"] = {k: v.get(k) for k in ("canonicalName", "id", "deprecated", "lzReadCompatible") if k in v}
        used = live["rayls_receive_uln"]["dvns"] + live["rayls_send_uln"]["dvns"]
        live["dvn_registry"] = {a: names.get(f"rayls:{a}") for a in sorted(set(used))}
        json.dump({k: v for k, v in meta.items() if k in ("rayls", "polygon")}, open(os.path.join(HERE, "raw", "dvn_metadata_rayls_polygon.json"), "w"), indent=1)
    except Exception as e:
        live["dvn_registry"] = str(e)[:100]
    live["supply_matches_rebuilt"] = live["brl1p_supply"] == supply
    live["lockbox_matches_rebuilt"] = live["lockbox_brl1"] == lockbox
    log(f"\n[3] Live state: lockbox {fmt(live['lockbox_brl1'])} (publicnode {fmt(live['lockbox_brl1_publicnode'])}), "
        f"BRL1.p supply {fmt(live['brl1p_supply'])} (explorer {live['brl1p_supply_explorer'] if isinstance(live['brl1p_supply_explorer'], str) else fmt(live['brl1p_supply_explorer'])})")
    log(f"    live equals rebuilt-from-events: lockbox {live['lockbox_matches_rebuilt']}, supply {live['supply_matches_rebuilt']}")
    log(f"    roles {live['roles']}; impl {live['brl1p_impl']}; adapter owner {live['adapter_owner']}; delegate {live['adapter_delegate']}")
    log(f"    Rayls receive ULN {live['rayls_receive_uln']}")
    log(f"    Rayls send ULN {live['rayls_send_uln']}")
    log(f"    DVN names in LayerZero's registry now: {live['dvn_registry']}")

    # ---- Polygon state at 00:00 UTC every day since the lockbox existed (archive, two providers)
    t0 = block_ts(p_url, LOCKBOX_FROM, pcache)
    day = (t0 // 86400 + 1) * 86400
    days = []
    while day <= block_ts(p_url, p_head, pcache):
        days.append(day)
        day += 86400
    daily = []
    lo = LOCKBOX_FROM
    for d in days:
        b = block_at(p_url, d, lo, p_head, pcache)
        lo = b
        row = {"date_utc": utc(d)[:10], "polygon_block": b}
        for n, url in POLY_ARCHIVE.items():
            try:
                bal = int(call(url, BRL1, "0x70a08231" + w(LOCKBOX), b), 16)
                row[f"lockbox_{n}"] = fmt(bal)
            except Exception as e:
                row[f"lockbox_{n}"] = "error"
        try:
            url = POLY_ARCHIVE["drpc"]
            row["lockbox_owner"] = addr(call(url, LOCKBOX, "0x8da5cb5b", b))
            row["lockbox_peer_rayls"] = addr(call(url, LOCKBOX, "0xbb0b6a53" + u32(EID_RAYLS), b))
            row["lockbox_delegate"] = addr(call(url, EP_POLYGON, "0x587cde1e" + w(LOCKBOX), b))
            lib = addr(call(url, EP_POLYGON, "0x402f8468" + w(LOCKBOX) + u32(EID_RAYLS), b)[:66])
            cfg = decode_uln(call(url, EP_POLYGON, "0x2b3197b9" + w(LOCKBOX) + w(lib) + u32(EID_RAYLS) + u32(2), b))
            slib = addr(call(url, EP_POLYGON, "0xb96a277f" + w(LOCKBOX) + u32(EID_RAYLS), b))
            scfg = decode_uln(call(url, EP_POLYGON, "0x2b3197b9" + w(LOCKBOX) + w(slib) + u32(EID_RAYLS) + u32(2), b))
            row["receive_dvns"] = f"{cfg['required']} req / {cfg['optional']} opt / {cfg['confirmations']} conf / " + " ".join(cfg["dvns"])
            row["send_dvns"] = f"{scfg['required']} req / {scfg['optional']} opt / {scfg['confirmations']} conf / " + " ".join(scfg["dvns"])
            row["brl1_paused"] = int(call(url, BRL1, "0x5c975abb", b), 16) == 1
        except Exception as e:
            row["config_error"] = str(e)[:100]
        # BRL1.p supply rebuilt from Rayls events up to that instant
        row["brl1p_supply_rebuilt"] = fmt(sum(dd["supply_delta"] for dd in ray_tx.values() if dd.get("supply_delta") and dd["ts"] <= d))
        daily.append(row)
    fields = []
    for r in daily:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(os.path.join(HERE, "data", "polygon_daily.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=fields)
        cw.writeheader()
        cw.writerows(daily)
    distinct = lambda k: sorted(set(r.get(k) for r in daily if r.get(k) not in (None, "0x" + "0" * 40)))
    log(f"\n[4] Polygon state at 00:00 UTC on {len(daily)} days ({daily[0]['date_utc']} to {daily[-1]['date_utc']})")
    log(f"    two archive providers agree on lockbox balance every day: {all(r.get('lockbox_drpc') == r.get('lockbox_tenderly') for r in daily)}")
    for k in ("lockbox_owner", "lockbox_peer_rayls", "lockbox_delegate", "receive_dvns", "send_dvns", "brl1_paused"):
        log(f"    distinct {k}: {distinct(k)}")
    log(f"    days with lockbox below rebuilt BRL1.p supply: {sum(1 for r in daily if r.get('lockbox_drpc') not in (None, 'error') and float(r['lockbox_drpc'].replace(',', '')) < float(r['brl1p_supply_rebuilt'].replace(',', '')))}")

    # ---- every admin / config event we can see
    cfg_rows = []
    for l in P["lockbox"]:
        nm = NAME.get(l["topics"][0], l["topics"][0])
        if nm not in ("OFTSent", "OFTReceived"):
            cfg_rows.append({"chain": "polygon", "contract": "lockbox", "event": nm, "block": int(l["blockNumber"], 16),
                             "time": utc(block_ts(p_url, int(l["blockNumber"], 16), pcache)), "tx": l["transactionHash"],
                             "topics": " ".join(l["topics"][1:]), "data": l["data"][:200]})
    for nm_c, logs_ in (("BRL1.p", rl_token), ("adapter", rl_adapter)):
        for l in logs_:
            nm = NAME.get(l["topics"][0], l["topics"][0])
            if nm not in ("OFTSent", "OFTReceived", "Transfer"):
                cfg_rows.append({"chain": "rayls", "contract": nm_c, "event": nm, "block": l["block_number"],
                                 "time": utc(block_ts(RAYLS_RPC, l["block_number"], rcache)), "tx": l["transaction_hash"],
                                 "topics": " ".join(t for t in l["topics"][1:] if t), "data": (l["data"] or "")[:200]})
    # LayerZero endpoint and ULN library events on Rayls that name the adapter
    for label, a in (("endpoint", ep_r), ("receive_uln", rlib), ("send_uln", slib)):
        try:
            for l in explorer_logs(a):
                if ADAPTER[2:] in (l["data"] or "").lower() or any(ADAPTER[2:] in (t or "") for t in l["topics"]):
                    nm = NAME.get(l["topics"][0], l["topics"][0])
                    if nm in ("PacketSent", "PacketDelivered", "PacketVerified") or l["topics"][0] in ("0x1ab700d4ced0c005b164c0f789fd09fcbb0156d4c2041b8a3bfbcd961cd1567f", "0x3cd5e48f9730b129dc7550f0fcea9c767b7be37837cd10e55eb35f734f4bca04", "0x0d87345f3d1c929caba93e1c3821b54ff3512e12b66aa3cfe54b6bcbc17e59b4"):
                        continue
                    cfg_rows.append({"chain": "rayls", "contract": label, "event": nm, "block": l["block_number"],
                                     "time": utc(block_ts(RAYLS_RPC, l["block_number"], rcache)), "tx": l["transaction_hash"],
                                     "topics": " ".join(t for t in l["topics"][1:] if t), "data": (l["data"] or "")[:200]})
        except Exception as e:
            log(f"    could not list {label} logs: {str(e)[:80]}")
    cfg_rows.sort(key=lambda r: r["time"])
    with open(os.path.join(HERE, "data", "config_events.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=["time", "chain", "contract", "event", "block", "tx", "topics", "data"])
        cw.writeheader()
        cw.writerows(cfg_rows)
    log(f"\n[5] Admin and config events: {len(cfg_rows)}")
    for r in cfg_rows:
        log(f"    {r['time']} {r['chain']:7s} {r['contract']:11s} {r['event']}  tx {r['tx']}")
    last_cfg = cfg_rows[-1]["time"] if cfg_rows else None
    log(f"    most recent admin/config event: {last_cfg}")

    summary = {
        "run_utc": utc(started), "polygon_block": p_head, "rayls_block": r_head,
        "transfers": len(rows), "polygon_to_rayls": n_pr, "rayls_to_polygon": n_rp,
        "all_checks_pass": len(rows) - len(problems), "stray_lockbox_changes": len(stray_p), "stray_supply_changes": len(stray_r),
        "lz_scan_only": len(lz_only), "lockbox_now": fmt(live["lockbox_brl1"]), "supply_now": fmt(live["brl1p_supply"]),
        "min_gap": fmt(worst[0]), "min_gap_time": worst[1], "supply_ever_above_lockbox": worst[0] < 0,
        "latency_p2r": [lats[0], lats[len(lats) // 2], lats[-1]] if lats else None, "latency_r2p": latr,
        "polygon_providers_agree": same, "archive_check": arch, "rayls_rpc_getlogs": rpc_counts,
        "rayls_explorer_logs": {"brl1p": len(rl_token), "adapter": len(rl_adapter)},
        "daily_days": len(daily), "config_events": len(cfg_rows), "last_config_event": last_cfg,
        "seconds": round(time.time() - started),
    }
    json.dump(live, open(os.path.join(HERE, "data", "live.json"), "w"), indent=1, default=str)
    json.dump(summary, open(os.path.join(HERE, "data", "summary.json"), "w"), indent=1)
    log(f"\nfinished {utc(time.time())} ({summary['seconds']} s)")
    open(os.path.join(HERE, "runs", f"{stamp}.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LOG.append(traceback.format_exc())
        os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
        open(os.path.join(HERE, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-FAILED.txt"), "w").write("\n".join(LOG))
        raise
