# BRL1.p backing monitor · BRL1.p 背书持续核对

[English](#english) · [中文](#中文)

---

## English

**Question:** Is one snapshot enough to trust a bridged stablecoin's "1:1"? How do you check it continuously, record by record?

**Case:** BRL1.p on the Rayls Public Chain, a LayerZero lock-and-mint bridge of BRL1 (Polygon). This folder follows up [`2026-10-brl1p-backing`](../2026-10-brl1p-backing/), which took one snapshot on 2026-10-17.

Every script is read-only, uses only the Python standard library (plus `pycryptodome` for keccak in `signers.py`), and needs no wallet or API key. The workflow [`.github/workflows/brl1p-monitor.yml`](../.github/workflows/brl1p-monitor.yml) runs everything every 6 hours on GitHub Actions and commits the outputs here, so each run is a dated reading in the git history.

### What each script does

| Script | Output | What it answers |
|---|---|---|
| `collect.py` | `data/transfers.csv`, `data/timeline.csv`, `data/polygon_daily.csv`, `data/config_events.csv`, `data/live.json`, `data/summary.json`, `raw/logs.json` | Every bridge transfer paired across both chains by its LayerZero GUID; every change to the lockbox balance and to BRL1.p supply merged by time; Polygon state at 00:00 UTC every day from two archive providers; every admin or config event |
| `dvn.py` | `data/dvn_verifications.csv`, `data/dvn_contracts.json`, `data/rayls_receipts.csv` | Which DVN posted a verification for which message, when, with how many confirmations; each DVN contract's quorum, signers and admin events |
| `signers.py` | `data/dvn_signers.csv`, `data/rayls_inputs.csv` | The signing keys recovered from each verification transaction (secp256k1 ecrecover, written out in the file), and whether the official Rayls RPC alone confirms each Rayls transaction |
| `admins.py` | `data/dvn_admins.json` | Which accounts hold `ADMIN_ROLE` on the six DVN contracts |
| `por.py`, `por_check.py` | `raw/por/`, `data/por_check.json` | The reserve pages and PoR files linked from brl1.io, and an archive check of each report's token figure |
| `build_data.py` | `data.json` | The figures the article and its two images quote, from the files above |
| `probe.py` | `results/probe-*.log` | Which public endpoints can answer which question |

### Recorded run: 2026-11-06

`collect.py` run at 03:25 UTC (Polygon block 96820054, Rayls block 13938544); `dvn.py` at 03:30; `signers.py` at 03:51; `admins.py` at 03:52; `por_check.py` at 03:56. Logs are in `runs/`. Later scheduled runs add files to `runs/` and overwrite `data/`; the article cites a commit, so the tables at that commit are the ones it quotes.

**1. Every transfer, paired by GUID.** 18 transfers since launch: 16 Polygon to Rayls (LayerZero nonces 1 to 16, no gaps) and 2 Rayls to Polygon (nonces 1 and 2). For all 18, the GUID in the source chain's `OFTSent` equals the GUID in the destination chain's `OFTReceived`, the amount locked or burned equals the amount minted or unlocked, and LayerZero Scan lists the same source and destination transaction hashes. No lockbox balance change and no BRL1.p supply change happened without a bridge message. Polygon to Rayls took 248 to 293 s (median 267 s); Rayls to Polygon took 57 and 63 s.

**2. One timeline across both chains.** 36 balance changes, merged by block time. After each one, the lockbox held at least as much BRL1 as there was BRL1.p; the smallest difference was 0. The rebuilt Polygon balance matched an archive `balanceOf` read at each of the 18 Polygon change blocks, from two providers (drpc and Tenderly), 0 mismatches. Daily reads at 00:00 UTC on 24 days (2026-10-14 to 2026-11-06) show the same lockbox owner, peer, LayerZero delegate and DVN configuration every day, and BRL1 never paused. All 18 admin or config events are from the 2026-10-13 setup (18:05 to 18:10 UTC); none since. Lockbox and supply on 2026-11-06: 255,291.961901 each.

**3. Who signed.** All 16 Polygon-to-Rayls messages carry a `PayloadVerified` on Rayls from each of the three required DVNs (48 events), and both Rayls-to-Polygon messages carry three on Polygon (6 events). Every one reports exactly the required confirmations: 120 Polygon blocks, or 10 Rayls blocks. On Rayls the verifications landed 232 to 253 s after the Polygon lock, which is where most of the bridge latency comes from.

Recovered signers (`data/dvn_signers.csv`):

| DVN (Rayls address) | Quorum now | Keys that signed |
|---|---|---|
| LayerZero Labs `0x396d…3f3c` | 2 of 3 | `0x0342…c164` and `0x238f…8ab5`, all 16 |
| Nethermind DVN, now listed as Twinstake `0x8d77…82dd` | 1 of 2 | `0xbbd4…95c9` for messages 1 to 4; `0x86f0…1d75` for 11 messages and `0x598c…64f7` for 1 from message 5 on |
| Canary `0xd01a…5b12` | 1 of 1 | `0x6d69…3d80`, all 16 |

The Nethermind-id DVN changed its signer set on both chains between 2026-10-14 19:55 and 2026-10-15 00:30 UTC (two `UpdateSigner` additions, one removal), between BRL1.p messages 4 and 5. LayerZero's DVN registry named this address "Nethermind" in the 2026-10-17 run ([log](../2026-10-brl1p-backing/evidence/run_2026-10-17T0721Z.log)) and "Twinstake" (id still `nethermind`) on 2026-11-06 ([`raw/dvn_metadata_rayls_polygon.json`](raw/dvn_metadata_rayls_polygon.json)).

All 54 verification transactions were sent by the same account, `0xb8ff877ed78ba520ece21b1de7843a8a57ca47cb`. That account and `0xb52fa54fc261398058c3ac7b8dd442d7d8b9f0b6` hold `ADMIN_ROLE` on all six DVN contracts (three on each chain). Both are plain accounts with no code; `0xb8ff…` has sent 8,880,381 transactions on Polygon. In LayerZero's DVN contract, `execute` can only be called by an admin and only succeeds with a quorum of signer signatures, so an admin cannot verify a message on its own.

**4. Can the official Rayls RPC reproduce this?** Only partly. `mainnet-rpc.rayls.com` answered every historical `eth_call` with "state at block … is pruned", returned 0 logs for BRL1.p and the adapter across blocks 12,430,000 to 13,938,544, and returned no receipt for any of the 18 Rayls transactions. It did return all 18 transactions: all 16 deliveries carry the GUID and the recipient and amount in their input, and both sends carry the recipient and amount. Rayls event history in this folder therefore comes from `explorer.rayls.com`, cross-checked against LayerZero Scan, the RPC's transaction inputs, and the RPC's current `totalSupply`.

**5. Reserve reports.** On 2026-11-06 the newest PoR file downloadable from brl1.io is still the 2026-10-01 report, which says it was "prepared internally" and "has not yet been audited by an independent entity". brl1.io labels its links "Last PoR (Proof of Reserves) audited of BRL1". The "latest PoR" link on the How it works page points to a report dated 2025-04-14, also internal. One more link asks for a Google sign-in, and the Fact Finance reserves page linked from brl1.io returned HTTP 404. The token figures in both readable reports match archive `totalSupply` reads at the blocks they name, from two providers. BRL1 supply on Polygon on 2026-11-06 was 17,882,561.54, 501,177 more than in the 2026-10-01 report.

### Read on-chain vs. inferred

Read directly: every transfer, GUID, amount, latency, balance, configuration, verification, confirmation count, signer, signer change, admin role and transaction count above; the registry names on both dates; the text of the PoR files.

Inference or open: that the 2026-10-14 signer change and the registry rename reflect Nethermind handing its DVN to Twinstake (Nethermind announced on 2026-08-19 that it had stopped operating its LayerZero DVN); who operates `0xb8ff…`; who holds any signing key. A shared submitting account is a shared point for liveness, not for forging messages: that is my reading of the contract code and of LayerZero's DVN reference, not something observed.

### Sources

- LayerZero-v2, `messagelib/contracts/uln/dvn/DVN.sol` and `MultiSig.sol`, commit `9c741e7f9790639537b1710a203bcdfd73b0b9ac`: https://github.com/LayerZero-Labs/LayerZero-v2
- LayerZero DVN contract reference: https://docs.layerzero.network/v2/workers/off-chain/dvn-technical-reference
- LayerZero DVN registry: https://metadata.layerzero-api.com/v1/metadata/dvns
- LayerZero Scan API: https://scan.layerzero-api.com/v1
- crypto.news, Nethermind leaves LayerZero verifier role for Chainlink, 2026-08-19: https://crypto.news/nethermind-leaves-layerzero-verifier-role-chainlink/
- BRL1 site and PoR files, fetched 2026-11-06: https://brl1.io/en
- Center for Audit Quality, what the GENIUS Act requires of accountants, 2025-10-27: https://www.thecaq.org/audit-in-action-what-does-the-genius-act-require-of-accountants

---

## 中文

**问题：** 跨链稳定币的"1:1"，查一次快照够吗？怎样逐笔、持续地核对？

**案例：** Rayls 公链上的 BRL1.p，它是 Polygon 上巴西雷亚尔稳定币 BRL1 通过 LayerZero"锁定再铸造"跨过来的版本。本文件夹是 [`2026-10-brl1p-backing`](../2026-10-brl1p-backing/) 的后续，那一篇在 2026-10-17 拍了一次快照。

所有脚本都是只读的，只用 Python 标准库（`signers.py` 另需 `pycryptodome` 计算 keccak），不需要钱包或 API 密钥。工作流 [`.github/workflows/brl1p-monitor.yml`](../.github/workflows/brl1p-monitor.yml) 每 6 小时在 GitHub Actions 上跑一遍并把结果提交回本仓库，所以每次运行都是 git 历史里一次带日期的读数。

### 各脚本做什么

| 脚本 | 输出 | 回答的问题 |
|---|---|---|
| `collect.py` | `data/transfers.csv` 等 | 用 LayerZero 消息编号（GUID）把每笔跨链在两条链上配对；把金库余额和 BRL1.p 发行量的每次变化按时间合并；每天 00:00 UTC 从两家归档节点读一次 Polygon 状态；列出所有管理和配置事件 |
| `dvn.py` | `data/dvn_verifications.csv` 等 | 哪个验证方（DVN）为哪笔消息提交了验证、何时、等了多少确认；每个 DVN 合约的签名门槛、签名人和管理事件 |
| `signers.py` | `data/dvn_signers.csv`、`data/rayls_inputs.csv` | 从每笔验证交易里还原签名密钥（secp256k1 公钥恢复，代码写在文件里）；只用 Rayls 官方节点能否确认每笔 Rayls 交易 |
| `admins.py` | `data/dvn_admins.json` | 六个 DVN 合约的 `ADMIN_ROLE` 在谁手里 |
| `por.py`、`por_check.py` | `raw/por/`、`data/por_check.json` | brl1.io 链接的储备页面和储备证明文件，以及每份报告里的代币数量与归档读数的核对 |
| `build_data.py` | `data.json` | 文章和两张配图引用的全部数字，都从上面这些文件汇总 |
| `probe.py` | `results/probe-*.log` | 哪些公共接口能回答哪类问题 |

### 记录的运行：2026-11-06

`collect.py` 于 03:25 UTC 运行（Polygon 区块 96820054，Rayls 区块 13938544），`dvn.py` 03:30，`signers.py` 03:51，`admins.py` 03:52，`por_check.py` 03:56，日志在 `runs/`。之后的定时运行会往 `runs/` 里加文件并覆盖 `data/`；文章引用的是某一次提交，那次提交里的表格就是文章所用的数据。

**1. 逐笔按 GUID 配对。** 上线以来共 18 笔：Polygon 到 Rayls 16 笔（LayerZero 序号 1 到 16，没有缺号），Rayls 到 Polygon 2 笔（序号 1 和 2）。18 笔全部满足：源链 `OFTSent` 里的 GUID 等于目标链 `OFTReceived` 里的 GUID，锁定或销毁的数量等于铸造或解锁的数量，LayerZero Scan 列出的两端交易哈希与链上一致。没有任何一次金库余额变化或 BRL1.p 发行量变化是没有跨链消息的。Polygon 到 Rayls 用时 248 到 293 秒，中位数 267 秒；Rayls 到 Polygon 用时 57 秒和 63 秒。

**2. 两条链合成一条时间线。** 36 次余额变化按区块时间排序。每一次变化之后，金库里的 BRL1 都不少于 BRL1.p 发行量，最小差值为 0。由事件重建的 Polygon 金库余额，在 18 个变化区块上与两家归档节点（drpc、Tenderly）的 `balanceOf` 读数逐一相符，0 处不符。24 天（2026-10-14 到 2026-11-06）每天 00:00 UTC 的读数显示，金库的所有者、对端、LayerZero 代理人和 DVN 配置每天都一样，BRL1 从未暂停。全部 18 条管理或配置事件都发生在 2026-10-13 18:05 到 18:10 UTC 的部署期间，之后没有新的。2026-11-06 金库与发行量均为 255,291.961901。

**3. 谁签的字。** 16 笔 Polygon 到 Rayls 的消息，在 Rayls 上都有三个必需 DVN 各自的 `PayloadVerified`（共 48 条）；2 笔 Rayls 到 Polygon 的消息在 Polygon 上各有三条（共 6 条）。每一条报告的确认数都正好等于要求：Polygon 120 个区块，Rayls 10 个区块。在 Rayls 上，验证在 Polygon 锁定后 232 到 253 秒到达，跨链耗时大部分就花在这里。

还原出的签名人见上方英文表格。id 为 `nethermind` 的 DVN 在 2026-10-14 19:55 到 2026-10-15 00:30 UTC 之间，在两条链上同时更换了签名人（新增两个、移除一个），正好在 BRL1.p 第 4 笔和第 5 笔消息之间。LayerZero 的 DVN 登记表在 2026-10-17 的运行里把这个地址标为"Nethermind"（[日志](../2026-10-brl1p-backing/evidence/run_2026-10-17T0721Z.log)），2026-11-06 标为"Twinstake"，id 仍是 `nethermind`（[`raw/dvn_metadata_rayls_polygon.json`](raw/dvn_metadata_rayls_polygon.json)）。

54 笔验证交易全部由同一个账户 `0xb8ff877ed78ba520ece21b1de7843a8a57ca47cb` 发出。这个账户和 `0xb52fa54fc261398058c3ac7b8dd442d7d8b9f0b6` 在全部六个 DVN 合约（每条链三个）上都持有 `ADMIN_ROLE`。两者都是没有合约代码的普通账户，`0xb8ff…` 在 Polygon 上已发出 8,880,381 笔交易。在 LayerZero 的 DVN 合约里，`execute` 只能由管理员调用，而且必须带够门槛数量的签名人签名才会成功，所以管理员自己无法验证一条消息。

**4. 官方 Rayls 节点能复现吗？** 只能部分复现。`mainnet-rpc.rayls.com` 对所有历史 `eth_call` 都返回"state at block … is pruned"（历史状态已裁剪），在 12,430,000 到 13,938,544 区块之间对 BRL1.p 和适配器返回 0 条日志，18 笔 Rayls 交易一笔回执都没有。但 18 笔交易本身都能查到：16 笔到账交易的输入数据里都有对应的 GUID、收款人和金额，2 笔发出交易的输入里也有收款人和金额。所以本文件夹里 Rayls 一侧的事件历史来自 `explorer.rayls.com`，再用 LayerZero Scan、官方节点的交易输入和当前 `totalSupply` 交叉核对。

**5. 储备报告。** 2026-11-06 能从 brl1.io 下载到的最新储备证明仍是 2026-10-01 那份，报告写明"内部编制"、"尚未经独立机构审计"，而 brl1.io 上的链接写的是"Last PoR (Proof of Reserves) audited of BRL1"。"运作方式"页面里"最新 PoR"的链接指向 2025-04-14 的报告，同样是内部编制。另有一个链接需要登录 Google，brl1.io 链接的 Fact Finance 储备页面返回 HTTP 404。两份可读报告里的代币数量，都与两家节点在报告所写区块上的 `totalSupply` 归档读数一致。2026-11-06 Polygon 上 BRL1 供应量为 17,882,561.54，比 10 月 1 日报告多 501,177。

### 链上读取 vs. 推断

直接读取：上面所有的转账、GUID、金额、耗时、余额、配置、验证、确认数、签名人、签名人变更、管理员角色和交易数；两个日期的登记表名称；储备文件的原文。

推断或未定：10 月 14 日的签名人更换和登记表改名，反映的是 Nethermind 把它的 DVN 交给了 Twinstake（Nethermind 于 2026-08-19 宣布停止运营 LayerZero DVN）；`0xb8ff…` 由谁运营；签名密钥由谁持有。共用一个提交账户影响的是"能不能及时送达"，而不是"能不能伪造消息"，这是我根据合约代码和 LayerZero 的 DVN 文档做的判断，不是观测结果。

### 来源

见英文部分。
