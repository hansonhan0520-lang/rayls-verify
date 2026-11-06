#!/usr/bin/env python3
"""Who actually signed each BRL1.p bridge message, and who controls those signers.

Runs after collect.py and reads its outputs (data/transfers.csv, data/live.json).
Read-only, standard library only.

Outputs:
  data/dvn_verifications.csv  one row per verifier per message: which DVN posted its
                              verification on the destination chain, in which tx, when,
                              and with how many source-chain confirmations
  data/dvn_contracts.json     for each of the six DVN contracts: current quorum and
                              signers, and every admin event found for it
  data/rayls_receipts.csv     each Rayls transaction re-read from the official RPC,
                              to see whether the RPC alone can confirm what the explorer shows
  runs/<time>-dvn.txt         human-readable log
"""
import calendar, csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as c

HERE = c.HERE
LOG = []


def log(s=""):
    LOG.append(s)
    print(s, flush=True)


PAYLOAD_VERIFIED = "0x2cb0eed7538baeae4c6fde038c0fd0384d27de0dd55a228c65847bda6aa1ab56"
DVN_EVENTS = {
    "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d": "RoleGranted",
    "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b": "RoleRevoked",
    "0x863d338cad74814b108a06288ad5e0e80d56495e0332238b1d2cdcfa0ca8e5ce": "UpdateSigner",
    "0xb600f3cf7f38a4b49bb0c75f722ef69f7e3e39ef3bb4aa8207fd86e724a23249": "UpdateQuorum",
    "0x7dd21e42791b013d1929e86f0c59085e4fca24251f0f1aa81917b3b1611766e0": "SetDstConfig",
    "0x1399be28223800f8669b3ba5f8721d9fc16fc4e8d0bbf98378791c8c5a3015e0": "SetWorkerLib",
    "0xf724a45d041687842411f2b977ef22ab8f43c8f1104f4592b42a00f9b34a643d": "SetPriceFeed",
    "0x62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a258": "Paused",
    "0x5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa": "Unpaused",
    "0x7af0ac740036ffb1c97b03697859d729e80a44ae5030543d64971c313565ab4d": "SetDefaultMultiplierBps",
    "0x9b1bfa7fa9ee420a16e124f794c35ac9f90472acc99140eb2f6447c714cad8eb": "Withdraw",
    "0xdc8cdd96296241bbefda4a8e18ad2e0985a8da6495b34d409cfc4c886ee3b0cf": "ExecuteFailed",
    "0x76831db4c0106418f393903ef4fb6ad12e860b251810c6ed3ed24a5f27593e90": "HashAlreadyUsed",
}
ROLES = {"0x" + "0" * 64: "DEFAULT_ADMIN",
         "0xa49807205ce4d355092ef5a8a18f56e8913cf4a201fbe287825b095693c21775": "ADMIN_ROLE",
         "0x724aface199fe5bed93ae8508474576a9adf3dc443b2c451842a2242919f19de": "MESSAGE_LIB_ROLE",
         "0x74845de37cfabd357633214b47fa91ccd19b05b7c5a08ac22c187f811fb62bca": "ALLOWLIST",
         "0x4270fae16c6d150d00e80b689daca99e8073b1838ff2b6063a37be9d851283e4": "DENYLIST"}


def decode_pv(data):
    h = data[2:]
    wd = lambda i: h[64 * i:64 * i + 64]
    dvn = "0x" + wd(0)[-40:]
    off = int(wd(1), 16) * 2
    conf = int(wd(2), 16)
    proof = "0x" + wd(3)
    ln = int(h[off:off + 64], 16)
    hdr = h[off + 64:off + 64 + 2 * ln]
    nonce = int(hdr[2:18], 16)
    src_eid = int(hdr[18:26], 16)
    sender = "0x" + hdr[26:90][-40:]
    dst_eid = int(hdr[90:98], 16)
    receiver = "0x" + hdr[98:162][-40:]
    return dict(dvn=dvn, confirmations=conf, payload_hash=proof, nonce=nonce, src_eid=src_eid,
                sender=sender, dst_eid=dst_eid, receiver=receiver)


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    live = json.load(open(os.path.join(HERE, "data", "live.json")))
    rows = list(csv.DictReader(open(os.path.join(HERE, "data", "transfers.csv"))))
    meta = json.load(open(os.path.join(HERE, "raw", "dvn_metadata_rayls_polygon.json")))
    names = {}
    for chain in ("rayls", "polygon"):
        for a, v in meta[chain]["dvns"].items():
            names[(chain, a.lower())] = f"{v.get('canonicalName')} (id {v.get('id')})"
    p_url = c.POLY["tenderly"][0]
    pc, rc = {}, {}
    log(f"DVN check, run {c.utc(time.time())}; {len(rows)} transfers from data/transfers.csv")

    # ---- Rayls side: every PayloadVerified on the receive library for the adapter
    rlib = live["rayls_libs"]["receive"]
    pv = []
    for l in c.explorer_logs(rlib):
        if l["topics"][0] != PAYLOAD_VERIFIED:
            continue
        d = decode_pv(l["data"])
        if d["receiver"] != c.ADAPTER:
            continue
        d.update(chain="rayls", tx=l["transaction_hash"], block=l["block_number"],
                 time_s=c.block_ts(c.RAYLS_RPC, l["block_number"], rc))
        pv.append(d)
    log(f"Rayls: {len(pv)} PayloadVerified events for the adapter on receive library {rlib}")

    # ---- Polygon side: PayloadVerified for the lockbox, near each Rayls->Polygon delivery
    plib = c.addr(c.call(p_url, c.EP_POLYGON, "0x402f8468" + c.w(c.LOCKBOX) + c.u32(c.EID_RAYLS))[:66])
    for r in rows:
        if r["direction"] != "R->P":
            continue
        b = int(r["dst_block"])
        for l in c.rpc(p_url, "eth_getLogs", [{"address": plib, "fromBlock": hex(b - 400), "toBlock": hex(b), "topics": [PAYLOAD_VERIFIED]}]):
            d = decode_pv(l["data"])
            if d["receiver"] != c.LOCKBOX or d["nonce"] != int(r["nonce"]):
                continue
            d.update(chain="polygon", tx=l["transactionHash"], block=int(l["blockNumber"], 16),
                     time_s=c.block_ts(p_url, int(l["blockNumber"], 16), pc))
            pv.append(d)
    log(f"Polygon receive library {plib}: {sum(1 for d in pv if d['chain'] == 'polygon')} PayloadVerified events for the lockbox")

    # ---- join to transfers
    out = []
    per_msg = {}
    for d in pv:
        direction = "P->R" if d["chain"] == "rayls" else "R->P"
        r = next((x for x in rows if x["direction"] == direction and int(x["nonce"]) == d["nonce"]), None)
        src_t = calendar.timegm(time.strptime(r["src_time"], "%Y-%m-%dT%H:%M:%SZ")) if r else None
        o = {"direction": direction, "nonce": d["nonce"], "guid": r["guid"] if r else "", "dvn": d["dvn"],
             "dvn_registry_name_now": names.get((d["chain"], d["dvn"]), "not in registry"),
             "verify_tx": d["tx"], "verify_block": d["block"], "verify_time": c.utc(d["time_s"]),
             "seconds_after_source": (d["time_s"] - src_t) if src_t else "",
             "confirmations": d["confirmations"], "payload_hash": d["payload_hash"]}
        out.append(o)
        per_msg.setdefault((direction, d["nonce"]), set()).add(d["dvn"])
    out.sort(key=lambda o: (o["verify_time"], o["dvn"]))
    with open(os.path.join(HERE, "data", "dvn_verifications.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        cw.writeheader()
        cw.writerows(out)
    required = {"P->R": set(live["rayls_receive_uln"]["dvns"])}
    log(f"\n[1] Verifications per message (required set on Rayls: {sorted(required['P->R'])})")
    full = sum(1 for (dr, n), s in per_msg.items() if dr == "P->R" and s >= required["P->R"])
    log(f"    Polygon->Rayls messages with all three required DVNs on record: {full} of {sum(1 for r in rows if r['direction'] == 'P->R')}")
    log(f"    Rayls->Polygon messages with verifications found: {sum(1 for (dr, n) in per_msg if dr == 'R->P')} of {sum(1 for r in rows if r['direction'] == 'R->P')}, "
        f"{[sorted(s) for (dr, n), s in per_msg.items() if dr == 'R->P']}")
    for dvn in sorted(set(o["dvn"] for o in out)):
        mine = [o for o in out if o["dvn"] == dvn]
        secs = sorted(int(o["seconds_after_source"]) for o in mine if o["seconds_after_source"] != "")
        confs = sorted(set(o["confirmations"] for o in mine))
        log(f"    {dvn} {mine[0]['dvn_registry_name_now']}: {len(mine)} verifications, "
            f"seconds after source min/median/max {secs[0]}/{secs[len(secs)//2]}/{secs[-1]}, confirmations {confs}")

    # ---- the DVN contracts themselves
    dvns = {"rayls": sorted(set(live["rayls_receive_uln"]["dvns"]) | set(live["rayls_send_uln"]["dvns"])),
            "polygon": ["0x13feb7234ff60a97af04477d6421415766753ba3", "0x23de2fe932d9043291f870324b74f820e11dc81a",
                        "0x31f748a368a893bdb5abb67ec95f232507601a73"]}
    info = {}
    p_head = int(c.rpc(p_url, "eth_blockNumber", []), 16) - 10
    p_from = c.block_at(p_url, 1780272000, 85000000, p_head, pc)   # 2026-06-01 00:00 UTC
    log(f"\n[2] DVN contracts (Polygon events searched from block {p_from}, 2026-06-01, to {p_head}; Rayls: all explorer logs)")
    for chain, addrs in dvns.items():
        url = c.RAYLS_RPC if chain == "rayls" else p_url
        for a in addrs:
            d = {"chain": chain, "address": a, "registry_name_now": names.get((chain, a), "not in registry")}
            for k, sel in (("quorum", "0x1703a018"), ("signer_size", "0xfd62e750"), ("vid", "0xcf34c768"), ("paused", "0x5c975abb")):
                try:
                    d[k] = int(c.call(url, a, sel), 16)
                except Exception as e:
                    d[k] = "error " + str(e)[:60]
            try:
                raw = c.call(url, a, "0x94cf795e")[2:]
                n = int(raw[64:128], 16)
                d["signers"] = ["0x" + raw[128 + 64 * i:192 + 64 * i][-40:] for i in range(n)]
            except Exception as e:
                d["signers"] = "error " + str(e)[:60]
            evs = []
            if chain == "rayls":
                logs = [{"topics": l["topics"], "data": l["data"], "tx": l["transaction_hash"], "block": l["block_number"]} for l in c.explorer_logs(a)]
            else:
                logs = []
                for b in range(p_from, p_head + 1, 10000):
                    for l in c.rpc(p_url, "eth_getLogs", [{"address": a, "fromBlock": hex(b), "toBlock": hex(min(b + 9999, p_head))}]):
                        logs.append({"topics": l["topics"], "data": l["data"], "tx": l["transactionHash"], "block": int(l["blockNumber"], 16)})
            counts = {}
            for l in logs:
                nm = DVN_EVENTS.get(l["topics"][0], l["topics"][0][:10])
                counts[nm] = counts.get(nm, 0) + 1
                if nm in ("RoleGranted", "RoleRevoked", "UpdateSigner", "UpdateQuorum", "Paused", "Unpaused", "SetWorkerLib"):
                    e = {"event": nm, "tx": l["tx"], "block": l["block"],
                         "time": c.utc(c.block_ts(url, l["block"], rc if chain == "rayls" else pc))}
                    if nm in ("RoleGranted", "RoleRevoked"):
                        e["role"] = ROLES.get(l["topics"][1], l["topics"][1])
                        e["account"] = "0x" + l["topics"][2][-40:]
                    elif nm == "UpdateSigner":
                        e["signer"] = "0x" + l["data"][2:66][-40:]
                        e["active"] = int(l["data"][66:130], 16) == 1
                    elif nm == "UpdateQuorum":
                        e["quorum"] = int(l["data"], 16)
                    evs.append(e)
            d["event_counts"] = counts
            d["admin_events"] = sorted(evs, key=lambda e: e["time"])
            info[f"{chain}:{a}"] = d
            last = d["admin_events"][-1] if d["admin_events"] else None
            log(f"    {chain:7s} {a} {d['registry_name_now']}: quorum {d['quorum']} of {d['signer_size']} signers, "
                f"{len(logs)} logs {counts}; last admin event {last['time'] + ' ' + last['event'] if last else 'none in range'}")
            for e in d["admin_events"]:
                if e["time"] >= "2026-06-01":
                    log(f"        {e}")
    json.dump(info, open(os.path.join(HERE, "data", "dvn_contracts.json"), "w"), indent=1)

    # ---- can the official Rayls RPC confirm the Rayls transactions on its own?
    rl = json.load(open(os.path.join(HERE, "raw", "logs.json")))
    exp_count = {}
    for l in rl["rayls_brl1p"] + rl["rayls_adapter"]:
        exp_count[l["transaction_hash"]] = exp_count.get(l["transaction_hash"], 0) + 1
    rec = []
    for r in rows:
        tx = r["dst_tx"] if r["direction"] == "P->R" else r["src_tx"]
        o = {"direction": r["direction"], "nonce": r["nonce"], "rayls_tx": tx, "explorer_logs_for_brl1p_and_adapter": exp_count.get(tx, 0)}
        try:
            t = c.rpc(c.RAYLS_RPC, "eth_getTransactionByHash", [tx])
            o["rpc_tx_found"] = bool(t)
        except Exception as e:
            o["rpc_tx_found"] = "error " + str(e)[:60]
        try:
            rc_ = c.rpc(c.RAYLS_RPC, "eth_getTransactionReceipt", [tx])
            mine = [l for l in rc_["logs"] if l["address"].lower() in (c.BRL1P, c.ADAPTER)]
            o.update(rpc_receipt_found=True, rpc_status=int(rc_["status"], 16), rpc_logs_for_brl1p_and_adapter=len(mine))
        except Exception as e:
            o.update(rpc_receipt_found=False, rpc_error=str(e)[:80])
        rec.append(o)
    fields = []
    for o in rec:
        fields += [k for k in o if k not in fields]
    with open(os.path.join(HERE, "data", "rayls_receipts.csv"), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=fields)
        cw.writeheader()
        cw.writerows(rec)
    ok = sum(1 for o in rec if o.get("rpc_receipt_found") is True and o.get("rpc_logs_for_brl1p_and_adapter") == o["explorer_logs_for_brl1p_and_adapter"])
    log(f"\n[3] Official Rayls RPC: transaction found {sum(1 for o in rec if o.get('rpc_tx_found') is True)} of {len(rec)}, "
        f"receipt found {sum(1 for o in rec if o.get('rpc_receipt_found') is True)} of {len(rec)}, "
        f"receipt logs equal explorer logs {ok} of {len(rec)}")
    errs = sorted(set(o.get("rpc_error", "") for o in rec if o.get("rpc_error")))
    if errs:
        log(f"    RPC errors seen: {errs}")
    log(f"\nfinished {c.utc(time.time())}")
    open(os.path.join(HERE, "runs", f"{stamp}-dvn.txt"), "w").write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
