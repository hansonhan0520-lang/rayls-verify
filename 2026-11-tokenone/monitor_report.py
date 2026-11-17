#!/usr/bin/env python3
"""Build a privacy-preserving monitor report without changing the article snapshot.

Set RAYLS_AUDIT_OUT to the directory where tokenone.py and vaults_audit.py just
wrote their data/. The default is this folder, which also allows an offline check
against the publication snapshot itself. No network requests or private keys.
"""
import json
import os
import time

H = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.environ.get("RAYLS_AUDIT_OUT", H)
ZERO = "0x0000000000000000000000000000000000000000"


def load(root, name):
    with open(os.path.join(root, "data", name)) as f:
        return json.load(f)


def token_summary(token):
    return {
        "supply": token["total_supply"],
        "holder_count": len(token["holders_now"]),
        "holders_sum_equals_supply": token["holders_sum_equals_supply"],
        "transfers_excluding_mint": len(token["transfers_excluding_mint"]),
        "paused": token["paused"],
        "compliance": token["compliance"],
        "compliance_configured": token["compliance"].lower() != ZERO,
        "roles": token["roles"],
        "rpc_log_count_matches_explorer": token["rpc_getlogs_matches_explorer_transfer_count"],
    }


def vault_summary(vault):
    return {
        "asset_symbol": vault["asset"]["symbol"],
        "idle_assets": vault["idle_assets_text"],
        "deployed_capital": vault["deployed_capital_text"],
        "total_assets": vault["total_assets_text"],
        "idle_balance_matches_rpc": vault["idle_balance_matches_rpc"],
        "total_assets_formula_matches": vault["total_assets_formula_matches"],
        "paused": vault["paused"],
        "roles": vault["roles"],
        "explorer_log_count": vault["event_log_count"],
        "manager_flows": [
            {
                "manager": flow["manager"],
                "received_from_vault": flow["received_from_vault_text"],
                "burned": flow["burned_text"],
                "returned": flow["returned_to_vault_text"],
                "minted_to_manager": flow["minted_to_manager_text"],
                "current_balance": flow["manager_asset_balance_text"],
                "withdrawal_transfers_match_events": flow["withdrawal_transfers_match_events"],
                "return_transfers_match_events": flow["return_transfers_match_events"],
                "asset_flow_reconciliation_matches_balance": flow["asset_flow_reconciliation_matches_balance"],
            }
            for flow in vault["manager_asset_flows"]
        ],
    }


def seed_summary(seed):
    return {
        "balance": seed["balance_text"],
        "incoming_transfer_count": seed["incoming_transfer_count"],
        "outgoing_transfer_count": seed["outgoing_transfer_count"],
        "unique_incoming_source_count": seed["unique_incoming_source_count"],
        "balance_matches_transfers": seed["balance_matches_transfers"],
        "lock_end_utc": seed["lock_end_utc"],
    }


def differences(old, new):
    """Return only changed scalar or JSON fields, labelled by their two snapshots."""
    changed = {}
    for key in sorted(set(old) | set(new)):
        if old.get(key) != new.get(key):
            changed[key] = {"publication": old.get(key), "latest": new.get(key)}
    return changed


def main():
    tokens = load(OUT_ROOT, "tokens.json")
    vaults = load(OUT_ROOT, "vaults.json")
    publication_tokens = load(H, "tokens.json")
    publication_vaults = load(H, "vaults.json")

    token_now = {k: token_summary(v) for k, v in tokens["tokens"].items()}
    token_then = {k: token_summary(v) for k, v in publication_tokens["tokens"].items()}
    vault_now = {k: vault_summary(v) for k, v in vaults["vaults"].items()}
    vault_then = {k: vault_summary(v) for k, v in publication_vaults["vaults"].items()}
    seed_now = seed_summary(vaults["launch_deposit_seed"])
    seed_then = seed_summary(publication_vaults["launch_deposit_seed"])

    changes = {
        "debentures": {k: differences(token_then.get(k, {}), v) for k, v in token_now.items()},
        "vaults": {k: differences(vault_then.get(k, {}), v) for k, v in vault_now.items()},
        "launch_deposit_seed": differences(seed_then, seed_now),
    }
    changes["debentures"] = {k: v for k, v in changes["debentures"].items() if v}
    changes["vaults"] = {k: v for k, v in changes["vaults"].items() if v}
    if not changes["launch_deposit_seed"]:
        changes.pop("launch_deposit_seed")

    token_checks = {
        f"{symbol}.holders_sum_equals_supply": row["holders_sum_equals_supply"]
        for symbol, row in token_now.items()
    }
    checks = dict(vaults["checks"])
    checks.update(token_checks)
    report = {
        "report_version": 1,
        "generated_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "publication_snapshot": {
            "run_utc": publication_tokens["run_utc"],
            "rayls_block": publication_tokens["rayls_block"],
        },
        "debenture_run": {
            "run_utc": tokens["run_utc"],
            "rayls_block": tokens["rayls_block"],
        },
        "vault_run": {
            "run_utc": vaults["run_utc"],
            "rayls_block": vaults["rayls_block"],
        },
        "debentures": token_now,
        "vaults": vault_now,
        "launch_deposit_seed": seed_now,
        "changes_vs_publication": changes,
        "state_changes_detected": any(bool(v) for v in changes.values()),
        "checks": checks,
        "monitor_checks_passed": all(checks.values()) and vaults["audit_checks_passed"],
        "privacy": "No VaultSeed depositor addresses or per-depositor amounts. Raw explorer responses remain outside the committed monitor output.",
        "note": "State changes are recorded, not treated as script failures. A green workflow requires successful reads and all accounting checks.",
    }

    os.makedirs(os.path.join(H, "data"), exist_ok=True)
    latest_path = os.path.join(H, "data", "monitor_latest.json")
    with open(latest_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write("\n")

    history = {
        "generated_utc": report["generated_utc"],
        "debenture_block": tokens["rayls_block"],
        "vault_block": vaults["rayls_block"],
        "state_changes_detected": report["state_changes_detected"],
        "monitor_checks_passed": report["monitor_checks_passed"],
        "debentures": {
            k: {x: row[x] for x in ("supply", "holder_count", "transfers_excluding_mint", "compliance_configured")}
            for k, row in token_now.items()
        },
        "vaults": {
            k: {x: row[x] for x in ("idle_assets", "deployed_capital", "total_assets", "explorer_log_count")}
            for k, row in vault_now.items()
        },
        "launch_deposit_seed": seed_now,
    }
    with open(os.path.join(H, "data", "monitor_history.jsonl"), "a") as f:
        f.write(json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(json.dumps({
        "generated_utc": report["generated_utc"],
        "debenture_block": tokens["rayls_block"],
        "vault_block": vaults["rayls_block"],
        "state_changes_detected": report["state_changes_detected"],
        "checks_passed": f"{sum(bool(x) for x in checks.values())}/{len(checks)}",
        "monitor_checks_passed": report["monitor_checks_passed"],
    }, ensure_ascii=False, indent=2))
    if not report["monitor_checks_passed"]:
        failed = [k for k, passed in checks.items() if not passed]
        raise RuntimeError("Monitor reconciliation failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
