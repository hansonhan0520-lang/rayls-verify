#!/usr/bin/env python3
"""Collect the figures the article and its two images quote into one file, data.json.
Reads only the files in data/ and raw/ produced by the scripts in this folder."""
import csv, json, os
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: list(csv.DictReader(open(os.path.join(H, "data", f))))
S = json.load(open(os.path.join(H, "data", "summary.json")))
L = json.load(open(os.path.join(H, "data", "live.json")))
tr, sg, ver, tl = rd("transfers.csv"), rd("dvn_signers.csv"), rd("dvn_verifications.csv"), rd("timeline.csv")
daily, inp = rd("polygon_daily.csv"), rd("rayls_inputs.csv")
dc = json.load(open(os.path.join(H, "data", "dvn_contracts.json")))
adm = json.load(open(os.path.join(H, "data", "dvn_admins.json")))
por = json.load(open(os.path.join(H, "data", "por_check.json")))
NAMES = {"0x396dc0a78f789586e2982fccd830c5954c193f3c": "LayerZero Labs", "0x8d77d35604a9f37f488e41d1d916b2a0088f82dd": "Nethermind/Twinstake",
         "0xd01ae6905d48315f7be10c7330aecf8360ef5b12": "Canary"}
matrix = []
for r in tr:
    if r["direction"] != "P->R":
        continue
    row = {"nonce": int(r["nonce"]), "time": r["src_time"], "amount": r["amount_locked_or_burned"], "latency_s": int(r["latency_s"])}
    for s in sg:
        if s["direction"] == "P->R" and s["nonce"] == r["nonce"]:
            row[NAMES[s["dvn"]]] = s["recovered_signers"].split()
    matrix.append(row)
ver_pr = [v for v in ver if v["direction"] == "P->R"]
secs = sorted(int(v["seconds_after_source"]) for v in ver_pr)
data = {
    "collect_run_utc": S["run_utc"], "polygon_block": S["polygon_block"], "rayls_block": S["rayls_block"],
    "transfers": S["transfers"], "p2r": S["polygon_to_rayls"], "r2p": S["rayls_to_polygon"], "all_pass": S["all_checks_pass"],
    "nonces_p2r": sorted(int(r["nonce"]) for r in tr if r["direction"] == "P->R"),
    "nonces_r2p": sorted(int(r["nonce"]) for r in tr if r["direction"] == "R->P"),
    "stray_lockbox": S["stray_lockbox_changes"], "stray_supply": S["stray_supply_changes"],
    "lockbox_now": S["lockbox_now"], "supply_now": S["supply_now"], "timeline_changes": len(tl),
    "supply_ever_above_lockbox": S["supply_ever_above_lockbox"], "archive_check": S["archive_check"],
    "latency_p2r": S["latency_p2r"], "latency_r2p": S["latency_r2p"],
    "daily_days": len(daily), "daily_from": daily[0]["date_utc"], "daily_to": daily[-1]["date_utc"],
    "daily_config_unchanged": all(len(set(d[k] for d in daily)) == 1 for k in ("lockbox_owner", "lockbox_peer_rayls", "lockbox_delegate", "receive_dvns", "send_dvns", "brl1_paused")),
    "config_events": S["config_events"], "last_config_event": S["last_config_event"],
    "roles": L["roles"], "admin": "0x633ac5e2315b973417e8caa6b3ad2162e0461ce1",
    "verifications": len(ver), "verifications_p2r": len(ver_pr), "verify_secs_p2r": [secs[0], secs[len(secs) // 2], secs[-1]],
    "confirmations": sorted(set(int(v["confirmations"]) for v in ver)),
    "submitters": sorted(set(s["submitted_by"] for s in sg)),
    "dvn": {k: {"quorum": v["quorum"], "signers": v["signers"], "registry_name_now": v["registry_name_now"],
                "admin_events_since_june": [e for e in v["admin_events"] if e["time"] >= "2026-06-01"]} for k, v in dc.items()},
    "dvn_admins": adm, "registry_name_2026_10_17": {"0x8d77d35604a9f37f488e41d1d916b2a0088f82dd": "Nethermind"},
    "matrix": matrix,
    "rayls_rpc": {"getlogs_logs": S["rayls_rpc_getlogs"], "historical_eth_call": "state at block ... is pruned (probe 2026-11-06)",
                  "tx_found": len(inp), "receipts_found": 0,
                  "input_guid": sum(1 for o in inp if o["input_has_guid"] == "True"),
                  "input_amount": sum(1 for o in inp if o["input_has_recipient_and_amount"] == "True")},
    "por": por,
}
json.dump(data, open(os.path.join(H, "data.json"), "w"), indent=1)
print(json.dumps({k: data[k] for k in ("transfers", "timeline_changes", "verify_secs_p2r", "confirmations", "submitters", "rayls_rpc", "daily_config_unchanged")}, indent=1))
for m in data["matrix"]:
    print(m["nonce"], m["time"], m["amount"], m["LayerZero Labs"], m["Nethermind/Twinstake"], m["Canary"])
