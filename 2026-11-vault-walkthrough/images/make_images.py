"""Render the two article images from rayls-verify 2026-11-vault-walkthrough/data/ (state.json, vault_events.csv)."""
import csv, json, sys
sys.path.insert(0, "/mnt/skills/plugins/rayls-rail-quest/scripts")
import brandkit as bk
LOGO = "/mnt/skills/plugins/rayls-rail-quest/assets/logo.png"
D = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "data")
s = json.load(open(f"{D}/state.json"))
c = s["layers_add_up"]
ev = list(csv.DictReader(open(f"{D}/vault_events.csv")))
fe = list(csv.DictReader(open(f"{D}/fund_events.csv")))
OUT = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
hms = lambda t: t[11:19]

# the 19 Nov afternoon round that settled the author's request (amount and time not shown on purpose)
st = next(r for r in ev if r["event"] == "SettleDeposit" and r["time_utc"].startswith("2026-11-19 15:"))
nav = [r for r in ev if r["event"] == "NewTotalAssetsUpdated" and r["time_utc"] <= st["time_utc"]][-1]
reqs = [r for r in ev if r["event"] == "DepositRequest" and nav["time_utc"][:10] == r["time_utc"][:10] and r["time_utc"] < nav["time_utc"] and r["time_utc"] > "2026-11-19 13:00:10"]
cl = [r for r in ev if r["event"] == "Deposit" and r["via"] == "claimSharesOnBehalf" and r["time_utc"] > st["time_utc"]][0]
inv = next(r for r in fe if r["event"] == "Deposit" and r["time_utc"] > st["time_utc"])

# ---------------- cover
cards = [("不到 2 小时", "从申请到结算（我这笔）", bk.YELLOW),
         ("8 秒", "结算后份额自动进钱包", bk.YELLOW),
         (f"差额 {abs(c['difference']):.0f}", "金库总资产 = 基金持仓折算", bk.PURPLE)]
W, H, y0, gap, M0 = 460, 214, 318, 40, 80
body = ""
for i, (big, small, col) in enumerate(cards):
    x = M0 + i * (W + gap)
    body += bk.rr(x, y0, W, H, 18, bk.BOX, col if i == 2 else "#2E2E36", 3 if i == 2 else 2)
    body += bk.text(x + 32, y0 + 100, big, col, 56, 800)
    body += bk.text(x + 32, y0 + 166, small, bk.WHITE, 26, 700)
bk.render_cover(f"{OUT}/vault-cover.png",
                title="存进 RWA 金库的钱去了哪？",
                subtitle="跟着自己的一笔存款，走完 Rayls TokenOne 金库 · 2026-11-19",
                body=body, footnote="先写预测再看结算：4 条对了 3 条 · 代码与每小时读数全部公开",
                logo_path=LOGO, title_size=54)

# ---------------- body: my deposit's path, 19 Nov times
steps = [
    ("1 申请", "Move to vault", f"下午 {len(reqs)} 笔转入进待处理仓，含我的", "下午", bk.WHITE),
    ("2 估值", "updateNewTotalAssets", "运营方加跑的一轮估值", hms(nav["time_utc"]), bk.YELLOW),
    ("3 结算", "settleDeposit · Safe", f"3 笔申请合计 {float(st['assets']):,.2f} 一起结算", hms(st["time_utc"]), bk.YELLOW),
    ("4 自动到账", "claimSharesOnBehalf", "三笔的份额一起发进各自钱包", hms(cl["time_utc"]), bk.YELLOW),
    ("5 投入基金", "TokenOne TIDC02", f"Safe 把 {float(inv['assets']):,.2f} 存进基金", hms(inv["time_utc"]), bk.PURPLE),
]
y, b = 404, ""
for i, (name, fn, desc, t, col) in enumerate(steps):
    h = 100
    b += bk.rr(90, y, 900, h, 16, bk.BOX, col if col != bk.WHITE else "#3A3A44", 3 if col != bk.WHITE else 2)
    b += bk.text(122, y + 44, name, bk.WHITE if col == bk.WHITE else col, 32, 800)
    b += bk.text(332, y + 44, fn, bk.GRAY, 24, 700)
    b += bk.text(958, y + 44, t, bk.WHITE if col == bk.WHITE else col, 28, 800, "end")
    b += bk.text(122, y + 82, desc, bk.WHITE, 26, 700)
    y += h
    if i < len(steps) - 1:
        b += f'<line x1="540" y1="{y + 2}" x2="540" y2="{y + 14}" stroke="{bk.GRAY}" stroke-width="4"/>'
        y += 16
y += 12
b += bk.rr(90, y, 900, 192, 16, bk.BOX, bk.PURPLE, 3)
b += bk.text(122, y + 46, "dapp 显示 vs 链上读到", bk.PURPLE, 30, 800)
b += bk.text(122, y + 90, "我的份额与价值", bk.WHITE, 26, 700)
b += bk.text(958, y + 90, "一致", bk.WHITE, 26, 800, "end")
b += bk.text(122, y + 128, "份额价格", bk.WHITE, 26, 700)
b += bk.text(958, y + 128, f"1.000625  |  {s['vault']['share_price']:.6f}", bk.WHITE, 26, 800, "end")
b += bk.text(122, y + 170, f"对账：金库 {c['vault_total_assets']:,.2f} = 基金持仓折算 {c['safe_position_at_fund_price']:,.2f}", bk.YELLOW, 24, 800)
bk.render_body(f"{OUT}/vault-body.png",
               title="我这笔存款，五步走完",
               subtitle="2026-11-19 下午那一轮的链上时间（UTC）",
               body=b, footnote="",
               source="rayls-verify · 2026-11-vault-walkthrough · vault.py",
               logo_path=LOGO)
print("ok", len(reqs))
