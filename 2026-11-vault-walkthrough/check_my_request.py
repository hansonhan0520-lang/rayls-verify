#!/usr/bin/env python3
"""Check your own position in the TokenOne pilot vault (TKONE02) on the Rayls Public Chain.

Usage:  python3 check_my_request.py 0xYOUR_ADDRESS

Read-only: it only reads public data, needs no key and sends nothing. It prints where your
deposit and redemption requests stand and how many shares you hold. Nothing is saved.

Stages of a deposit in an ERC-7540 vault:
  pending    your BRL1.p is waiting for the next settlement; you can still cancel
  claimable  the vault has settled it into shares at that day's price; claim them on the
             vault page (or they are claimed for you on your next deposit request)
  held       the shares are in your wallet and their value moves with the share price
"""
import json, sys, urllib.request

RPC = "https://mainnet-rpc.rayls.com"
VAULT = "0x1811630b90e6966573e809270a5e9316a25de6fe"
UA = {"User-Agent": "rayls-verify-check", "Content-Type": "application/json"}
SEL = {"pendingDepositRequest": "0x26c6f96c", "claimableDepositRequest": "0x995ea21a",
       "pendingRedeemRequest": "0xf5a23d8d", "claimableRedeemRequest": "0xeaed1d07",
       "balanceOf": "0x70a08231", "convertToAssets": "0x07a2d13a", "isAllowed": "0xbabcc539"}


def call(data):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": VAULT, "data": data}, "latest"]}).encode()
    with urllib.request.urlopen(urllib.request.Request(RPC, data=body, headers=UA), timeout=30) as r:
        return int(json.load(r)["result"], 16)


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith("0x") or len(sys.argv[1]) != 42:
        sys.exit("usage: python3 check_my_request.py 0xYOUR_ADDRESS")
    a = sys.argv[1].lower()[2:].rjust(64, "0")
    req = "0" * 64  # requestId 0 means "your latest request" in this vault
    f = lambda v: f"{v / 1e18:,.6f}"
    shares = call(SEL["balanceOf"] + a)
    print(f"whitelisted (KYC):               {bool(call(SEL['isAllowed'] + a))}")
    print(f"deposit pending settlement:      {f(call(SEL['pendingDepositRequest'] + req + a))} BRL1.p")
    print(f"deposit settled, shares to claim: {f(call(SEL['claimableDepositRequest'] + req + a))} BRL1.p worth")
    print(f"shares in your wallet:           {f(shares)} RLSTKONE02 (= {f(call(SEL['convertToAssets'] + format(shares, '064x')))} BRL1.p now)")
    print(f"redemption pending:              {f(call(SEL['pendingRedeemRequest'] + req + a))} shares")
    print(f"redemption ready to withdraw:    {f(call(SEL['claimableRedeemRequest'] + req + a))} shares")
    pending = call(SEL["pendingDepositRequest"] + req + a)
    if pending:
        price = call(SEL["convertToAssets"] + format(10 ** 18, "064x")) / 1e18
        print(f"\nAt today's share price ({price:.6f}) your pending deposit would become about "
              f"{pending / 1e18 / price:,.2f} shares. The real number uses the price set at settlement,")
        print("which so far has happened once a day at about 13:00 UTC; on 19 Nov the shares were then")
        print("claimed into depositors' wallets automatically 8 seconds later.")


if __name__ == "__main__":
    main()
