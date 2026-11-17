#!/usr/bin/env python3
"""Reconcile TokenOne-related RWA vaults and the separate Rayls launch-deposit contract.

Read-only. Public RPC and explorer APIs only; no wallet, key or API secret.
Requires pycryptodome for Keccak-256 function selectors.

Unlike the earlier discovery script, this audit follows explorer pagination. It reads every
vault log, every CapitalWithdrawn/CapitalReturned event, and every asset transfer of the
manager destinations. It separates three different quantities:
  * idleAssets: the asset balance actually held by the vault contract;
  * deployedCapital: an ORACLE_ROLE-reported value for assets outside the contract;
  * totalAssets: idleAssets + deployedCapital, as implemented by RwaVaultV3.

For BRLT vaults it also reconciles withdrawals with subsequent burns at the manager
wallets. A burn proves that the token left Rayls circulation. It does not identify the
off-chain receivable bought afterwards, and this script does not claim that it does.

The launch-deposit section deliberately publishes aggregates only, not depositor addresses.
Outputs: data/vaults.json, data/vault_capital_events.csv,
         data/manager_asset_transfers.csv, raw/audit/, runs/<time>-vaults-audit.txt
"""
import csv
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

from Crypto.Hash import keccak

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokenone as T

H = T.HERE
# Keep scheduled raw responses outside the repository. Only normalised public
# aggregates and transfer-level institutional records are selected for commit.
OUT_ROOT = os.environ.get("RAYLS_AUDIT_OUT", H)
OUT = os.path.join(OUT_ROOT, "raw", "audit")
ZERO = "0x" + "0" * 40
BRLT = "0xe14c117ea3eba1728cc8003590c04eb641f1e268"
BRL1P = "0xa069d3798feab32994ac5d98a9f011da6024f334"
SEED = "0x5b9565e27f5d50b14d3f660799f87e829a53fab2"
VAULTS = {
    "AMC01": "0x2bdbd4001eaf67077105b388a5cf2df26c65f1b7",
    "GIRU01": "0x84035676fa725c25346f91e17e4a9f1b41ab1f4f",
    "TKONE02": "0x870c2c4cfaf895f55163385813164e5808ae7029",
    "TKONE01": "0x8fff24202c1360324571df9ca8aff5137a963492",
}
LOG = []
ASSET_ROWS = []


def say(s=""):
    LOG.append(str(s))
    print(s, flush=True)


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(value, f, indent=1, ensure_ascii=False, default=str)


def selector(signature):
    h = keccak.new(digest_bits=256)
    h.update(signature.encode())
    return "0x" + h.digest()[:4].hex()


def uint(result):
    return int(result, 16) if isinstance(result, str) and result.startswith("0x") else None


def address(result):
    return T.addr(result).lower() if isinstance(result, str) and result.startswith("0x") else result


def string(result):
    if not isinstance(result, str) or not result.startswith("0x") or len(result) < 130:
        return result
    try:
        b = bytes.fromhex(result[2:])
        offset = int.from_bytes(b[:32], "big")
        size = int.from_bytes(b[offset:offset + 32], "big")
        return b[offset + 32:offset + 32 + size].decode(errors="replace")
    except Exception:
        return result


def call_uint(contract, signature, suffix=""):
    return uint(T.call(contract, selector(signature) + suffix))


def call_address(contract, signature):
    return address(T.call(contract, selector(signature)))


def call_string(contract, signature):
    return string(T.call(contract, selector(signature)))


def event_name(log):
    return (log.get("decoded") or {}).get("method_call", "").split("(")[0]


def event_params(log):
    return {p["name"]: p["value"] for p in (log.get("decoded") or {}).get("parameters", [])}


def amount_text(value, decimals):
    if value is None:
        return None
    q = Decimal(value) / (Decimal(10) ** decimals)
    return format(q, "f")


def transfer_amount(item):
    total = item.get("total")
    raw = total.get("value") if isinstance(total, dict) else item.get("value")
    return int(raw)


def asset_state(asset):
    return {
        "address": asset,
        "name": call_string(asset, "name()"),
        "symbol": call_string(asset, "symbol()"),
        "decimals": call_uint(asset, "decimals()"),
        "total_supply": call_uint(asset, "totalSupply()"),
        "paused": bool(call_uint(asset, "paused()")),
    }


def role_state(contract, signatures, candidates):
    roles = {}
    for name in signatures:
        role = T.call(contract, selector(name + "()"))
        if not role.startswith("0x"):
            continue
        holders = []
        for account in sorted(candidates):
            answer = T.call(contract, "0x91d14854" + role[2:] + T.w(account))
            if answer == T.TRUE:
                holders.append(account)
        roles[name] = {"hash": role, "holders": holders}
    return roles


def read_vault(symbol, vault):
    say(f"\n[{symbol}] {vault}")
    asset = call_address(vault, "asset()")
    asset_info = asset_state(asset)
    decimals = asset_info["decimals"]
    d = {
        "symbol": symbol,
        "address": vault,
        "name": call_string(vault, "name()"),
        "share_decimals": call_uint(vault, "decimals()"),
        "share_supply": call_uint(vault, "totalSupply()"),
        "asset": asset_info,
        "idle_assets": call_uint(vault, "idleAssets()"),
        "asset_balance_rpc": call_uint(asset, "balanceOf(address)", T.w(vault)),
        "deployed_capital": call_uint(vault, "deployedCapital()"),
        "total_assets": call_uint(vault, "totalAssets()"),
        "unbooked_assets": call_uint(vault, "unbookedAssets()"),
        "reported_at": call_uint(vault, "reportedAt()"),
        "max_report_age": call_uint(vault, "maxReportAge()"),
        "max_report_deviation_bps": call_uint(vault, "maxReportDeviationBps()"),
        "withdraw_policy": call_address(vault, "withdrawPolicy()"),
        "compliance": call_address(vault, "compliance()"),
        "paused": bool(call_uint(vault, "paused()")),
        "contract_uri": call_string(vault, "contractURI()"),
    }
    d["reported_at_utc"] = datetime.fromtimestamp(d["reported_at"], timezone.utc).isoformat()
    d["idle_balance_matches_rpc"] = d["idle_assets"] == d["asset_balance_rpc"]
    d["total_assets_formula_matches"] = d["total_assets"] == d["idle_assets"] + d["deployed_capital"]
    for key in ("idle_assets", "asset_balance_rpc", "deployed_capital", "total_assets", "unbooked_assets", "share_supply"):
        d[key + "_text"] = amount_text(d[key], decimals if key != "share_supply" else d["share_decimals"])

    logs = T.explorer_all(f"/addresses/{vault}/logs")
    save_json(os.path.join(OUT, f"{symbol}_logs.json"), logs)
    d["event_counts"] = dict(Counter(event_name(x) or (x.get("topics") or ["?"])[0] for x in logs))
    d["event_log_count"] = len(logs)
    role_candidates = {"0x14f918b1739e325ef588b725f1ee63c6215db335"}
    for log in logs:
        if event_name(log) in ("RoleGranted", "RoleRevoked"):
            p = event_params(log)
            if p.get("account") and p["account"].lower() != ZERO:
                role_candidates.add(p["account"].lower())
    d["roles"] = role_state(vault, ["DEFAULT_ADMIN_ROLE", "MANAGER_ROLE", "ORACLE_ROLE", "ENFORCER_ROLE", "PAUSER_ROLE", "ISSUER_ROLE"], role_candidates)
    d["role_account_kinds"] = {}
    for role in d["roles"].values():
        for account in role["holders"]:
            if account not in d["role_account_kinds"]:
                d["role_account_kinds"][account] = T.kind(account)

    capital_events = []
    managers = set()
    for log in sorted(logs, key=lambda x: (x["block_number"], x["index"])):
        name = event_name(log)
        if name not in ("CapitalWithdrawn", "CapitalReturned", "DeployedCapitalReported"):
            continue
        p = event_params(log)
        row = {
            "vault": symbol,
            "event": name,
            "block": log["block_number"],
            "timestamp": log["block_timestamp"],
            "tx": log["transaction_hash"],
        }
        for key in ("amount", "deployedCapital", "previous", "current"):
            if key in p:
                row[key] = int(p[key])
                row[key + "_text"] = amount_text(row[key], decimals)
        for key in ("to", "from"):
            if key in p:
                row[key] = p[key].lower()
        if name == "CapitalWithdrawn":
            managers.add(row["to"])
        capital_events.append(row)
    d["capital_withdrawn_total"] = sum(x.get("amount", 0) for x in capital_events if x["event"] == "CapitalWithdrawn")
    d["capital_returned_total"] = sum(x.get("amount", 0) for x in capital_events if x["event"] == "CapitalReturned")
    d["capital_withdrawn_total_text"] = amount_text(d["capital_withdrawn_total"], decimals)
    d["capital_returned_total_text"] = amount_text(d["capital_returned_total"], decimals)
    d["report_adjustment_vs_net_transfers"] = d["deployed_capital"] - d["capital_withdrawn_total"] + d["capital_returned_total"]
    d["report_adjustment_vs_net_transfers_text"] = amount_text(d["report_adjustment_vs_net_transfers"], decimals)

    flows = []
    for manager in sorted(managers):
        transfers = T.explorer_all(f"/addresses/{manager}/token-transfers")
        save_json(os.path.join(OUT, f"{symbol}_{manager[:10]}_asset_transfers.json"), transfers)
        burns = []
        returns = []
        mints = []
        vault_withdrawals = []
        other_incoming = []
        other_outgoing = []
        for item in transfers:
            token = (item.get("token") or {}).get("address_hash", "").lower()
            if token != asset.lower():
                continue
            fr = (item.get("from") or {}).get("hash", "").lower()
            to = (item.get("to") or {}).get("hash", "").lower()
            raw_amount = transfer_amount(item)
            ASSET_ROWS.append({
                "vault": symbol,
                "manager": manager,
                "asset": asset,
                "block": item.get("block_number"),
                "log_index": item.get("log_index"),
                "timestamp": item.get("timestamp"),
                "tx": item.get("transaction_hash"),
                "from": fr,
                "to": to,
                "amount": raw_amount,
                "amount_text": amount_text(raw_amount, decimals),
                "explorer_type": item.get("type"),
                "method": item.get("method"),
            })
            if fr == manager.lower() and to == ZERO:
                burns.append(item)
            elif fr == manager.lower() and to == vault.lower():
                returns.append(item)
            elif fr == ZERO and to == manager.lower():
                mints.append(item)
            elif fr == vault.lower() and to == manager.lower():
                vault_withdrawals.append(item)
            elif to == manager.lower():
                other_incoming.append(item)
            elif fr == manager.lower():
                other_outgoing.append(item)
        burned = sum(transfer_amount(x) for x in burns)
        returned = sum(transfer_amount(x) for x in returns)
        minted = sum(transfer_amount(x) for x in mints)
        received = sum(transfer_amount(x) for x in vault_withdrawals)
        other_in = sum(transfer_amount(x) for x in other_incoming)
        other_out = sum(transfer_amount(x) for x in other_outgoing)
        manager_balance = call_uint(asset, "balanceOf(address)", T.w(manager))
        reconciled_balance = received + minted + other_in - burned - returned - other_out
        flows.append({
            "manager": manager,
            "manager_kind": T.kind(manager),
            "vault_withdrawal_transfer_count": len(vault_withdrawals),
            "received_from_vault": received,
            "received_from_vault_text": amount_text(received, decimals),
            "withdrawal_transfers_match_events": received == d["capital_withdrawn_total"],
            "burn_count": len(burns),
            "burned": burned,
            "burned_text": amount_text(burned, decimals),
            "return_to_vault_count": len(returns),
            "returned_to_vault": returned,
            "returned_to_vault_text": amount_text(returned, decimals),
            "return_transfers_match_events": returned == d["capital_returned_total"],
            "minted_to_manager": minted,
            "minted_to_manager_text": amount_text(minted, decimals),
            "other_incoming": other_in,
            "other_outgoing": other_out,
            "manager_asset_balance": manager_balance,
            "manager_asset_balance_text": amount_text(manager_balance, decimals),
            "reconciled_asset_balance": reconciled_balance,
            "reconciled_asset_balance_text": amount_text(reconciled_balance, decimals),
            "asset_flow_reconciliation_matches_balance": manager_balance == reconciled_balance,
            "burn_txs": [x.get("transaction_hash") for x in burns],
            "return_txs": [x.get("transaction_hash") for x in returns],
            "mint_txs": [x.get("transaction_hash") for x in mints],
        })
    d["manager_asset_flows"] = flows
    d["manager_burned_total"] = sum(x["burned"] for x in flows)
    d["manager_burned_total_text"] = amount_text(d["manager_burned_total"], decimals)
    d["withdrawn_not_burned"] = d["capital_withdrawn_total"] - d["manager_burned_total"]
    d["withdrawn_not_burned_text"] = amount_text(d["withdrawn_not_burned"], decimals)
    say(f"    idle {d['idle_assets_text']} {asset_info['symbol']}; deployed {d['deployed_capital_text']}; total {d['total_assets_text']}")
    say(f"    withdrawals {d['capital_withdrawn_total_text']}; returns {d['capital_returned_total_text']}; manager burns {d['manager_burned_total_text']}")
    say(f"    totalAssets formula matches: {d['total_assets_formula_matches']}; events read: {len(logs)}")
    return d, capital_events


def read_brlt(candidates):
    d = asset_state(BRLT)
    d["whitelist_enabled"] = bool(call_uint(BRLT, "whitelistEnabled()"))
    d["mint_limit_per_period"] = call_uint(BRLT, "mintLimitPerPeriod()")
    d["mint_limit_period"] = call_uint(BRLT, "mintLimitPeriod()")
    logs = T.explorer_all(f"/addresses/{BRLT}/logs")
    role_logs = [x for x in logs if event_name(x) in ("RoleGranted", "RoleRevoked")]
    save_json(os.path.join(OUT, "BRLT_role_logs.json"), role_logs)
    for log in role_logs:
        account = event_params(log).get("account", "").lower()
        if account and account != ZERO:
            candidates.add(account)
    d["roles"] = role_state(BRLT, ["DEFAULT_ADMIN_ROLE", "MINTER_ROLE", "BURNER_ROLE", "PAUSER_ROLE", "COMPLIANCE_ROLE", "UPGRADER_ROLE", "BRIDGE_ROLE"], candidates)
    d["role_account_kinds"] = {}
    for role in d["roles"].values():
        for account in role["holders"]:
            if account not in d["role_account_kinds"]:
                d["role_account_kinds"][account] = T.kind(account)
    d["total_supply_text"] = amount_text(d["total_supply"], d["decimals"])
    return d


def read_seed():
    """Publish only contract-level aggregates. Never emit the depositors' addresses."""
    transfers = T.explorer_all(f"/addresses/{SEED}/token-transfers")
    incoming = outgoing = 0
    incoming_count = outgoing_count = 0
    sources = set()
    for item in transfers:
        if (item.get("token") or {}).get("address_hash", "").lower() != BRL1P:
            continue
        value = transfer_amount(item)
        fr = (item.get("from") or {}).get("hash", "").lower()
        to = (item.get("to") or {}).get("hash", "").lower()
        if to == SEED:
            incoming += value
            incoming_count += 1
            sources.add(fr)
        elif fr == SEED:
            outgoing += value
            outgoing_count += 1
    logs = T.explorer_all(f"/addresses/{SEED}/logs")
    lock_events = [x for x in logs if event_name(x) == "LockEndSet"]
    limit_events = [x for x in logs if event_name(x) == "LimitsSet"]
    lock_end = None
    if lock_events:
        latest = max(lock_events, key=lambda x: (x["block_number"], x["index"]))
        lock_end = int(event_params(latest)["lockEnd"])
    limits = None
    if limit_events:
        latest = max(limit_events, key=lambda x: (x["block_number"], x["index"]))
        limits = {k: int(v) for k, v in event_params(latest).items()}
    balance = call_uint(BRL1P, "balanceOf(address)", T.w(SEED))
    d = {
        "address": SEED,
        "asset": BRL1P,
        "asset_decimals": 18,
        "balance": balance,
        "balance_text": amount_text(balance, 18),
        "incoming_transfer_count": incoming_count,
        "outgoing_transfer_count": outgoing_count,
        "unique_incoming_source_count": len(sources),
        "incoming_total": incoming,
        "outgoing_total": outgoing,
        "incoming_total_text": amount_text(incoming, 18),
        "outgoing_total_text": amount_text(outgoing, 18),
        "balance_matches_transfers": balance == incoming - outgoing,
        "lock_end": lock_end,
        "lock_end_utc": datetime.fromtimestamp(lock_end, timezone.utc).isoformat() if lock_end else None,
        "latest_limits": limits,
        "privacy": "Aggregates only; depositor addresses and per-depositor amounts are intentionally not written to output.",
    }
    say(f"\n[VaultSeed] balance {d['balance_text']} BRL1.p; {incoming_count} incoming, {outgoing_count} outgoing; lock end {d['lock_end_utc']}")
    return d


def main():
    stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())
    for directory in ("data", "runs", "raw/audit"):
        os.makedirs(os.path.join(OUT_ROOT, directory), exist_ok=True)
    head = int(T.rpc("eth_blockNumber", []), 16)
    run_utc = T.utc(time.time())
    say(f"RWA vault audit, run {run_utc}, Rayls block {head}")
    result = {"run_utc": run_utc, "rayls_block": head, "vaults": {}}
    all_events = []
    candidates = {"0x14f918b1739e325ef588b725f1ee63c6215db335"}
    for symbol, vault in VAULTS.items():
        d, events = read_vault(symbol, vault)
        result["vaults"][symbol] = d
        all_events.extend(events)
        for role in d["roles"].values():
            candidates.update(role["holders"])
    result["brlt"] = read_brlt(candidates)
    result["launch_deposit_seed"] = read_seed()
    result["brlt_vaults_withdrawn_total"] = sum(d["capital_withdrawn_total"] for d in result["vaults"].values() if d["asset"]["address"].lower() == BRLT)
    result["brlt_vaults_returned_total"] = sum(d["capital_returned_total"] for d in result["vaults"].values() if d["asset"]["address"].lower() == BRLT)
    result["brlt_vaults_manager_burned_total"] = sum(d["manager_burned_total"] for d in result["vaults"].values() if d["asset"]["address"].lower() == BRLT)
    result["brlt_vaults_withdrawn_less_burns"] = result["brlt_vaults_withdrawn_total"] - result["brlt_vaults_manager_burned_total"]
    for key in ("brlt_vaults_withdrawn_total", "brlt_vaults_returned_total", "brlt_vaults_manager_burned_total", "brlt_vaults_withdrawn_less_burns"):
        result[key + "_text"] = amount_text(result[key], 6)
    result["checks"] = {}
    for symbol, vault_data in result["vaults"].items():
        result["checks"][f"{symbol}.idle_balance_matches_rpc"] = vault_data["idle_balance_matches_rpc"]
        result["checks"][f"{symbol}.total_assets_formula_matches"] = vault_data["total_assets_formula_matches"]
        for index, flow in enumerate(vault_data["manager_asset_flows"]):
            for field in ("withdrawal_transfers_match_events", "return_transfers_match_events", "asset_flow_reconciliation_matches_balance"):
                result["checks"][f"{symbol}.manager_{index}.{field}"] = flow[field]
    result["checks"]["VaultSeed.balance_matches_transfers"] = result["launch_deposit_seed"]["balance_matches_transfers"]
    result["audit_checks_passed"] = all(result["checks"].values())
    save_json(os.path.join(OUT_ROOT, "data", "vaults.json"), result)
    fields = ["vault", "event", "block", "timestamp", "tx", "to", "from", "amount", "amount_text", "deployedCapital", "deployedCapital_text", "previous", "previous_text", "current", "current_text"]
    with open(os.path.join(OUT_ROOT, "data", "vault_capital_events.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_events)
    asset_fields = ["vault", "manager", "asset", "block", "log_index", "timestamp", "tx", "from", "to", "amount", "amount_text", "explorer_type", "method"]
    with open(os.path.join(OUT_ROOT, "data", "manager_asset_transfers.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=asset_fields)
        writer.writeheader()
        writer.writerows(sorted(ASSET_ROWS, key=lambda x: (x["block"], x["log_index"], x["tx"])))
    say(f"\nBRLT vault totals: withdrawn {result['brlt_vaults_withdrawn_total_text']}; returned {result['brlt_vaults_returned_total_text']}; manager burns {result['brlt_vaults_manager_burned_total_text']}")
    say(f"Withdrawn less burns is arithmetic only, not a residual-balance claim: {result['brlt_vaults_withdrawn_less_burns_text']}")
    say(f"All reconciliation checks passed: {result['audit_checks_passed']}")
    say(f"finished {T.utc(time.time())}")
    with open(os.path.join(OUT_ROOT, "runs", f"{stamp}-vaults-audit.txt"), "w") as f:
        f.write("\n".join(LOG) + "\n")
    if not result["audit_checks_passed"]:
        failed = [name for name, passed in result["checks"].items() if not passed]
        raise RuntimeError("Vault reconciliation failed: " + ", ".join(failed))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LOG.append(traceback.format_exc())
        os.makedirs(os.path.join(OUT_ROOT, "runs"), exist_ok=True)
        with open(os.path.join(OUT_ROOT, "runs", time.strftime("%Y-%m-%dT%H%MZ", time.gmtime()) + "-vaults-audit-FAILED.txt"), "w") as f:
            f.write("\n".join(LOG) + "\n")
        raise
