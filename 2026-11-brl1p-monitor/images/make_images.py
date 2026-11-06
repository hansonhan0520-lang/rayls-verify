"""Render the two article images from ../data.json. Needs the brandkit.py helper and the official Rayls logo file (not in this repo)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/claude/skill/rayls-rail-quest/scripts")
import brandkit as bk
LOGO = "/home/claude/skill/rayls-rail-quest/assets/logo.png"
d = json.load(open(os.path.join(HERE, "..", "data.json")))

# ---------------- cover
cards = [(f"{d['all_pass']} / {d['transfers']}", "笔跨链在两条链上逐笔对上", bk.YELLOW),
         ("0 次", f"{d['timeline_changes']} 次余额变化中发行量超过金库", bk.YELLOW),
         ("1 个", "必须签字的验证方换了签名密钥", bk.PURPLE)]
W, H, y0, gap, M0 = 460, 214, 318, 40, 80
body = ""
for i, (big, small, col) in enumerate(cards):
    x = M0 + i * (W + gap)
    body += bk.rr(x, y0, W, H, 18, bk.BOX, col if i == 2 else "#2E2E36", 3 if i == 2 else 2)
    body += bk.text(x + 32, y0 + 104, big, col, 64, 800)
    body += bk.text(x + 32, y0 + 168, small, bk.WHITE, 26, 700)
foot = f"{d['verifications']} 次验证签名逐一还原，全部由同一个账户提交 · 代码与逐笔记录全部公开"
bk.render_cover(os.path.join(HERE, "brl1p-monitor-cover.png"),
                title="跨链稳定币的 1:1，查一次够吗？",
                subtitle="BRL1.p 上线以来 18 笔跨链逐笔核对 · 2026-11-06",
                body=body, footnote=foot, logo_path=LOGO, title_size=54)

# ---------------- body: who signed each Polygon -> Rayls message
short = lambda a: a[:6]
X = [90, 145, 265, 470, 700, 900]   # column x: nonce, date, amount, LZ, Nethermind/Twinstake, Canary
y = 420
b = ""
heads = [("#", bk.GRAY), ("日期", bk.GRAY), ("金额", bk.GRAY), ("LayerZero Labs", bk.GRAY), ("Nethermind", bk.GRAY), ("Canary", bk.GRAY)]
for (h, col), x in zip(heads, X):
    b += bk.text(x, y, h, col, 24, 700)
b += bk.text(X[4], y + 30, "→ Twinstake", bk.PURPLE, 24, 700)
b += f'<line x1="90" y1="{y + 48}" x2="990" y2="{y + 48}" stroke="{bk.RULE}" stroke-width="2"/>'
y += 80
RH = 34
for m in d["matrix"]:
    if m["nonce"] == 5:
        b += f'<line x1="90" y1="{y - 26}" x2="990" y2="{y - 26}" stroke="{bk.PURPLE}" stroke-width="3" stroke-dasharray="10 8"/>'
        b += bk.text(X[4] - 8, y + 2, "10月14日 19:55 至 15日 00:30 换签名人", bk.PURPLE, 24, 800, "middle")
        y += 42
    mo, dd = int(m["time"][5:7]), int(m["time"][8:10])
    tw = m["Nethermind/Twinstake"][0]
    twcol = bk.GRAY if tw.startswith("0xbbd4") else bk.PURPLE
    b += bk.text(X[0], y, str(m["nonce"]), bk.GRAY, 24, 700)
    b += bk.text(X[1], y, f"{mo}/{dd}", bk.WHITE, 24, 700)
    amt = float(m["amount"].replace(",", ""))
    b += bk.text(X[2], y, f"{amt:,.2f}", bk.WHITE, 24, 700)
    b += bk.text(X[3], y, " ".join(short(a) for a in m["LayerZero Labs"]), bk.YELLOW, 24, 700, font=bk.MONO)
    b += bk.text(X[4], y, short(tw), twcol, 24, 700, font=bk.MONO)
    b += bk.text(X[5], y, short(m["Canary"][0]), bk.YELLOW, 24, 700, font=bk.MONO)
    y += RH
lz = d["dvn"]["rayls:0x396dc0a78f789586e2982fccd830c5954c193f3c"]
tw = d["dvn"]["rayls:0x8d77d35604a9f37f488e41d1d916b2a0088f82dd"]
ca = d["dvn"]["rayls:0xd01ae6905d48315f7be10c7330aecf8360ef5b12"]
b += f'<line x1="90" y1="{y - 18}" x2="990" y2="{y - 18}" stroke="{bk.RULE}" stroke-width="2"/>'
b += bk.text(X[2], y + 12, "验证门槛", bk.GRAY, 24, 700)
b += bk.text(X[3], y + 12, f"{lz['quorum']} / {len(lz['signers'])} 签", bk.GRAY, 24, 700)
b += bk.text(X[4], y + 12, f"{tw['quorum']} / {len(tw['signers'])} 签", bk.GRAY, 24, 700)
b += bk.text(X[5], y + 12, f"{ca['quorum']} / {len(ca['signers'])} 签", bk.GRAY, 24, 700)
bk.render_body(os.path.join(HERE, "brl1p-monitor-body.png"),
               title="每笔跨链是谁签的字",
               subtitle="Polygon 到 Rayls 的 16 笔，从验证交易里还原的签名人",
               body=b,
               footnote=f"三个验证方的 {d['verifications']} 次验证，全部由同一账户 {d['submitters'][0][:6]}…{d['submitters'][0][-4:]} 提交",
               source="rayls-verify · 2026-11-brl1p-monitor · dvn_signers.csv · 2026-11-06",
               logo_path=LOGO)
print("ok", y)
