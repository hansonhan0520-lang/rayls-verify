#!/usr/bin/env python3
"""Build the single data file used by the article, images and X thread.

This script performs no network requests. It reads the dated outputs from
tokenone.py, vaults_audit.py and cvm_registry.py, checks the figures used in
the publication, and writes data.json beside this file.
"""
import csv
import json
import os
from decimal import Decimal

H = os.path.dirname(os.path.abspath(__file__))
ZERO = "0x0000000000000000000000000000000000000000"


def load(name):
    with open(os.path.join(H, "data", name)) as f:
        return json.load(f)


def dec(value):
    return Decimal(str(value))


def display(value):
    """Group an exact decimal without changing its significant fractional digits."""
    d = dec(value)
    text = format(d, ",f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


tokens = load("tokens.json")
vaults = load("vaults.json")
cvm = load("cvm.json")
with open(os.path.join(H, "data", "vault_capital_events.csv")) as f:
    capital_events = list(csv.DictReader(f))
with open(os.path.join(H, "data", "manager_asset_transfers.csv")) as f:
    manager_asset_transfers = list(csv.DictReader(f))

assert tokens["rayls_block"] == vaults["rayls_block"]
assert tokens["run_utc"] == vaults["run_utc"]
assert vaults["audit_checks_passed"] is True

bond_output = {}
for symbol, token in tokens["tokens"].items():
    assert token["holders_sum_equals_supply"] is True
    assert len(token["holders_now"]) == 1
    assert len(token["transfers_excluding_mint"]) == 0
    bond_output[symbol] = {
        "address": token["address"],
        "supply": display(token["total_supply"]),
        "holder_count": len(token["holders_now"]),
        "holder_addresses": sorted(token["holders_now"]),
        "transfers_excluding_mint": len(token["transfers_excluding_mint"]),
        "mint_tx": token["mints"][0]["tx"],
        "compliance": token["compliance"],
        "compliance_configured": token["compliance"].lower() != ZERO,
        "can_transfer_holder_to_stranger": token["simulations"].get("token.canTransfer(holder->stranger, 1)"),
        "roles": token["roles"],
        "rpc_getlogs_transfer_events": token["rpc_getlogs_transfer_events"],
        "explorer_transfer_events": token["explorer_event_counts"].get("Transfer", 0),
        "rpc_log_count_matches_explorer": token["rpc_getlogs_matches_explorer_transfer_count"],
    }

supply_total = sum(dec(x["total_supply"]) for x in tokens["tokens"].values())
assert supply_total == Decimal("35000000")

vault_output = {}
for symbol, vault in vaults["vaults"].items():
    assert vault["idle_balance_matches_rpc"] is True
    assert vault["total_assets_formula_matches"] is True
    assert all(flow["asset_flow_reconciliation_matches_balance"] for flow in vault["manager_asset_flows"])
    vault_output[symbol] = {
        "address": vault["address"],
        "name": vault["name"],
        "asset_symbol": vault["asset"]["symbol"],
        "asset_address": vault["asset"]["address"],
        "idle_assets": display(vault["idle_assets_text"]),
        "deployed_capital": display(vault["deployed_capital_text"]),
        "total_assets": display(vault["total_assets_text"]),
        "reported_at_utc": vault["reported_at_utc"],
        "max_report_age_seconds": vault["max_report_age"],
        "max_report_deviation_bps": vault["max_report_deviation_bps"],
        "withdraw_policy": vault["withdraw_policy"],
        "withdrawn": display(vault["capital_withdrawn_total_text"]),
        "returned": display(vault["capital_returned_total_text"]),
        "manager_burned": display(vault["manager_burned_total_text"]),
        "manager_flows": [
            {
                "manager": flow["manager"],
                "received_from_vault": display(flow["received_from_vault_text"]),
                "burned": display(flow["burned_text"]),
                "returned": display(flow["returned_to_vault_text"]),
                "minted_to_manager": display(flow["minted_to_manager_text"]),
                "current_balance": display(flow["manager_asset_balance_text"]),
                "reconciled_balance": display(flow["reconciled_asset_balance_text"]),
                "checks_passed": all(flow[k] for k in (
                    "withdrawal_transfers_match_events",
                    "return_transfers_match_events",
                    "asset_flow_reconciliation_matches_balance",
                )),
            }
            for flow in vault["manager_asset_flows"]
        ],
        "roles": vault["roles"],
        "explorer_log_count": sum(vault["event_counts"].values()),
        "event_counts": vault["event_counts"],
        "contract_uri": vault["contract_uri"],
    }

# A compact worked example: every BRLT withdrawn from TKONE01 is accounted for
# by burns, returns and the manager's remaining balance. This is vault-specific;
# it must not be applied to AMC01, whose 11 BRLT return was newly minted first.
t1 = vaults["vaults"]["TKONE01"]
f1 = t1["manager_asset_flows"][0]
tkone01_identity_left = dec(t1["capital_withdrawn_total_text"])
tkone01_identity_right = dec(f1["burned_text"]) + dec(f1["returned_to_vault_text"]) + dec(f1["manager_asset_balance_text"])
assert tkone01_identity_left == tkone01_identity_right

all_log_count = sum(sum(v["event_counts"].values()) for v in vaults["vaults"].values())
assert all_log_count == 343
assert len(capital_events) == 164
assert len(manager_asset_transfers) == 38

entry = cvm["entries"][0]
seed = vaults["launch_deposit_seed"]
data = {
    "question": "RWA 上链后，投资人到底能在链上核对什么？",
    "run_utc": tokens["run_utc"],
    "rayls_block": tokens["rayls_block"],
    "debentures": bond_output,
    "debenture_supply_total": display(supply_total),
    "debenture_holder_count_each": 1,
    "debenture_transfers_excluding_mint_total": 0,
    "vaults": vault_output,
    "vault_count": len(vault_output),
    "vault_explorer_logs_total": all_log_count,
    "vault_capital_event_rows": len(capital_events),
    "manager_asset_transfer_rows": len(manager_asset_transfers),
    "vault_reconciliation_checks": len(vaults["checks"]),
    "vault_reconciliation_checks_passed": vaults["audit_checks_passed"],
    "brlt_vaults": {
        "withdrawn": display(vaults["brlt_vaults_withdrawn_total_text"]),
        "returned": display(vaults["brlt_vaults_returned_total_text"]),
        "manager_burned": display(vaults["brlt_vaults_manager_burned_total_text"]),
        "note": "These are separate flow totals, not a residual-balance equation. AMC01 returned 11 BRLT that had first been minted to its manager.",
    },
    "tkone01_reconciliation": {
        "withdrawn": display(t1["capital_withdrawn_total_text"]),
        "burned": display(f1["burned_text"]),
        "returned": display(f1["returned_to_vault_text"]),
        "manager_balance": display(f1["manager_asset_balance_text"]),
        "equation": f"{display(t1['capital_withdrawn_total_text'])} = {display(f1['burned_text'])} + {display(f1['returned_to_vault_text'])} + {display(f1['manager_asset_balance_text'])}",
        "asset_symbol": "BRLT",
    },
    "launch_deposit_seed": {
        "address": seed["address"],
        "asset_symbol": "BRL1.p",
        "balance": display(seed["balance_text"]),
        "incoming_transfer_count": seed["incoming_transfer_count"],
        "outgoing_transfer_count": seed["outgoing_transfer_count"],
        "unique_incoming_source_count": seed["unique_incoming_source_count"],
        "balance_matches_transfers": seed["balance_matches_transfers"],
        "lock_end_utc": seed["lock_end_utc"],
        "privacy": seed["privacy"],
    },
    "cvm": {
        "checked_utc": cvm["checked_utc"],
        "source": cvm["source"],
        "name": entry["denominacaoSocial"],
        "cnpj": entry["numeroRegistroFormatado"],
        "status": entry["tipoSituacaoRegistroDescricao"],
        "cvm_code": entry["codigoCVM"],
        "registration_date": entry["dataRegistro"][:10],
        "process": entry["numeroProcesso"],
        "note": cvm["note"],
    },
    "evidence_limits": {
        "rpc_logs": "The official RPC returned zero Transfer logs for all three debentures although the explorer has one mint log each. RPC log search is diagnostic only, not absence evidence.",
        "burns": "A burn proves that tokens left on-chain circulation. It does not identify an off-chain receivable, legal settlement or investor beneficial ownership.",
        "deployed_capital": "deployedCapital is reported by ORACLE_ROLE. The contract can enforce accounting rules around the report but cannot verify the external asset itself.",
        "metadata": "The four contractURI values were recorded. IPFS metadata was not retrieved, so its contents are not asserted.",
    },
}

out = os.path.join(H, "data.json")
with open(out, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps({
    "run_utc": data["run_utc"],
    "rayls_block": data["rayls_block"],
    "debenture_supply_total": data["debenture_supply_total"],
    "vault_explorer_logs_total": all_log_count,
    "vault_capital_event_rows": len(capital_events),
    "checks": f"{len(vaults['checks'])}/{len(vaults['checks'])}",
    "tkone01_equation": data["tkone01_reconciliation"]["equation"],
}, ensure_ascii=False, indent=2))
