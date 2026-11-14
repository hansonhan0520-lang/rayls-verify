# RLS lock-up check · RLS 锁仓核对

[English](#english) · [中文](#中文)

---

## English

**Question:** When a project says tokens are locked, how can anyone check on-chain that they really are, and whether the lock can be opened early?

**Case:** Parfin's 1,070,493,535 RLS, which Rayls announced on 2026-08-06 had been moved into an on-chain lock on the Rayls Public Chain with the first release pushed to December 2027; and the 2026-10-29 announcement that investors and team extend their vesting too.

**Answer in one line:** check three layers, not one. The lock contract here does exactly what it says. The RLS it holds is an upgradeable token on Rayls whose every role sits with one plain account. The bridge backing on Ethereum adds up.

Everything here is read-only. No wallet, no key, no API key. Simulated transactions use `eth_call`: the node executes the call against current state and throws the result away; nothing is signed or sent. The workflow [`.github/workflows/rls-vesting-monitor.yml`](../.github/workflows/rls-vesting-monitor.yml) runs the four checks every 6 hours and commits the results, so each run is a dated reading in git history.

### Scripts

| Script | Output | What it answers |
|---|---|---|
| `probe.py` | `raw/probe/`, `runs/*-probe.txt` | The transparency page is a single-page app; this saves its scripts, lists the data endpoints they call, and saves the lock contract's explorer record, including its verified source |
| `portal.py` | `raw/portal/<time>/` | The portal's numbers straight from `api.rayls.com/v1/dashboard/*` and the `metric-overrides.json` file the page merges on top |
| `lock.py` | `data/lock_state.json`, `data/lock_schedule.csv`, `data/lock_roles.csv`, `data/lock_funding.csv` | The lock's terms, all 48 dates, every owner/admin change, every RLS transfer in or out, and simulated claims (now, one second before the first date, at the first, 12th and last dates, using a block-timestamp override) |
| `rls_token.py` | `data/token_state.json` | How the lock's RLS reached Rayls: the three LayerZero messages of 2026-08-05, from LayerZero Scan |
| `roles.py` | `data/roles_state.json`, `data/rls_roles.csv` | Who holds each role on RLS on Rayls; the bridge adapters on both chains; RLS locked on Ethereum against RLS supply on Rayls and BSC |
| `powers.py` | `data/powers.json` | What the accounts that control RLS on Rayls can do to the lock's balance, simulated |
| `build_data.py` | `data.json` | Every figure the article and its two images quote, from the files above |
| `images/make_images.py` | `images/*.png` | The two article images, drawn from `data.json` |

### Findings (readings 2026-11-11 16:04 UTC to 2026-11-14 03:00 UTC)

**1. The lock contract.** `RlsTokenLock` at `0x1463889D3a5EAAEE3f066d1CF438A8957F7Db98E`, verified on the Rayls explorer, not a proxy. It holds 1,070,493,535 RLS, exactly its `totalAmount`; funded on 2026-08-06 in three transfers (10, 500,000,000 and 570,493,525 RLS). 48 release dates, 00:00 UTC on the 1st of every month from 2027-12-01 to 2031-11-01. Nothing has been claimed or burned. Simulations: an admin claiming now reverts `NotYetVested(2027-12-01)`; one second before the first date also reverts; at the first date it returns 22,301,948.645833 RLS (1/48); at the 12th date 267,623,383.75; at the last date the whole amount. A non-admin cannot claim, burn or add admins.

The contract does have privileged accounts: 3 owners and 5 admins, all plain single-key accounts. Admins can claim released tranches to themselves (the contract has no fixed beneficiary) and can burn still-locked tokens; owners manage both lists. None of them can release anything before its date. The 2026-08-06 announcement said the contract "contains no admin keys"; that is true of upgrade and schedule changes, not of these roles.

**2. The token the lock holds.** RLS on Rayls (`0x07E17e17…17Ea`) is an OpenZeppelin UUPS proxy (`RLS`, version 2.0.0) with five roles. The lock's RLS was minted on Rayls on 2026-08-05 by three LayerZero messages from the Ethereum adapter `0x3ea6bac7…aba6` (370,493,535 + 350,000,000 + 350,000,000). One plain account, `0x0e301bEEF8daaD28f8e38D9fce09112b78fE3161`, holds DEFAULT_ADMIN, UPGRADER, MINTER, BURNER and PAUSER, and owns `ElevatedMinterBurner` (`0xe4854d19…f609`), the contract the bridge adapter mints and burns through. In this token's source, a MINTER or BURNER can `burnFrom` any account without an allowance. Simulated from that account: `burnFrom(lock, 1 RLS)` succeeds, `mint` succeeds, `upgradeToAndCall` succeeds; the same calls from an unrelated address revert. The same account is an owner and admin of the lock and one of six signers of the Ethereum Safe.

**3. The bridge and Ethereum.** The Ethereum adapter is owned by a Safe that needs 4 of 6 signatures, and RLS on Ethereum (`0xb5f7b021…4fbd`) is not a proxy; its roles sit with the same Safe, and its only mint (the full 10 billion) has already happened. On 2026-11-14 03:00 UTC the Ethereum adapter held 1,571,189,488.404144 RLS against 1,376,174,564.894676 on Rayls plus 195,014,762.160717 on BSC: 161.348751 RLS more than the two spokes together (the same surplus on 2026-11-11 16:18 UTC). Both adapters name the same plain account `0x633Ac5e2…ce1` as LayerZero delegate, which can change their messaging configuration; three DVNs are required each way.

**4. Investors and team.** As of 2026-11-14 no lock address for these allocations has been published. A search of the Rayls explorer for `RlsTokenLock` returns only the Parfin contract.

**5. Over three days.** Nine readings: lock balance, schedule, owners and admins unchanged; RLS roles unchanged in all nine complete role readings (the first, at 16:18 UTC on 2026-11-11, checked fewer accounts). The portal's circulating supply rose by exactly 50,000,000 RLS between 2026-11-11 16:24 and 2026-11-12 00:59 UTC; its cause is not traced here.

### Read on-chain vs. inferred

Read directly: every balance, date, role, transfer and simulation result above. Inferred or open: who holds any key; any off-chain agreement covering the tokens; whether investor and team allocations are locked anywhere. A simulation shows what an account can do, not what anyone intends.

### Sources

- Rayls, Parfin extends $RLS lock-up by one year and migrates allocation on-chain to Rayls, 2026-08-06: https://www.rayls.com/blog/parfin-extends-rls-lock-up-by-one-year-and-migrates-allocation-onchain-to-rayls
- Rayls, Rayls investors and team also extend $RLS vesting, 2026-10-29: https://www.rayls.com/blog/rayls-investors-and-team-extend-rls-vesting
- RLS transparency portal: https://transparency.rayls.com/
- Rayls explorer API: https://explorer.rayls.com/api/v2
- LayerZero Scan API: https://scan.layerzero-api.com/v1
- Sourcify (RLS on Ethereum): https://sourcify.dev

---

## 中文

**问题：** 项目方说币锁住了，任何人怎么在链上确认真的锁住了，以及这把锁能不能被提前打开？

**案例：** Parfin 的 1,070,493,535 枚 RLS。Rayls 在 2026-08-06 宣布这批币已迁入 Rayls 公链上的链上锁仓，首次释放推迟到 2027 年 12 月；10 月 29 日又宣布投资人和团队也延长解锁。

**一句话答案：** 要查三层，不能只查一层。这里的锁仓合约完全按说的做；但它锁着的是 Rayls 上一个可升级的代币，这个代币的全部权限都在一个普通钱包手里；以太坊上的跨链背书对得上。

所有脚本只读，不需要钱包、私钥或 API 密钥。模拟交易用 `eth_call`：节点按当前状态试算一遍就丢掉，不签名、不上链。工作流 [`.github/workflows/rls-vesting-monitor.yml`](../.github/workflows/rls-vesting-monitor.yml) 每 6 小时跑一遍四项检查并把结果提交回仓库，每次运行都是 git 历史里一条带日期的读数。

### 发现（读数时间 2026-11-11 16:04 UTC 至 2026-11-14 03:00 UTC）

**1. 锁仓合约。** `RlsTokenLock`，地址 `0x1463889D3a5EAAEE3f066d1CF438A8957F7Db98E`，源码已在 Rayls 区块浏览器验证，不是代理合约。合约里有 1,070,493,535 枚 RLS，正好等于它记录的总额；2026-08-06 分三笔转入（10 枚、5 亿枚、570,493,525 枚）。共 48 个释放日期，从 2027-12-01 到 2031-11-01，每月 1 日 00:00 UTC。至今没有领取，也没有销毁。模拟结果：管理员现在领取，返回 `NotYetVested(2027-12-01)` 被拒；把时间拨到首个日期前 1 秒，仍被拒；拨到首个日期，正好领出 22,301,948.645833 枚（1/48）；到第 12 个日期累计 267,623,383.75 枚；到最后一个日期是全部。非管理员不能领取、不能销毁、不能加管理员。

合约确实有特权账户：3 个所有者、5 个管理员，全是单签普通钱包。管理员可以把已到期的部分领给自己（合约没有固定收款方），也可以销毁尚未解锁的币；所有者负责增删这两份名单。他们都不能让任何一笔提前释放。8 月 6 日的公告说合约"没有管理员密钥"，这对"升级"和"改时间表"成立，对这些角色不成立。

**2. 被锁的代币。** Rayls 上的 RLS（`0x07E17e17…17Ea`）是 OpenZeppelin UUPS 可升级代理（`RLS`，2.0.0 版），有五种角色。锁里的 RLS 是 2026-08-05 由以太坊适配器 `0x3ea6bac7…aba6` 发出的三条 LayerZero 消息在 Rayls 上铸造的（370,493,535 + 3.5 亿 + 3.5 亿）。一个普通钱包 `0x0e301bEEF8daaD28f8e38D9fce09112b78fE3161` 同时握有 DEFAULT_ADMIN、UPGRADER、MINTER、BURNER、PAUSER 五种权限，还是跨链桥铸造与销毁所经由的 `ElevatedMinterBurner`（`0xe4854d19…f609`）的所有者。这个代币的源码规定，MINTER 或 BURNER 不需要授权就能 `burnFrom` 任何地址。从该账户模拟：`burnFrom(锁仓合约, 1 枚)` 成功，`mint` 成功，`upgradeToAndCall` 成功；同样的调用换成无关地址全部被拒。这个账户同时是锁仓合约的所有者和管理员，也是以太坊多签的 6 个签名人之一。

**3. 跨链桥与以太坊。** 以太坊适配器归一个 6 人多签（需 4 人签字）所有；以太坊上的 RLS（`0xb5f7b021…4fbd`）不是代理合约，权限也在这个多签手里，唯一一次铸造（全部 100 亿枚）早已完成。2026-11-14 03:00 UTC，以太坊适配器锁着 1,571,189,488.404144 枚，Rayls 上发行 1,376,174,564.894676 枚，BSC 上 195,014,762.160717 枚，以太坊比两条链合计多 161.348751 枚（2026-11-11 16:18 UTC 也是这个数）。两边适配器的 LayerZero 代理人都是同一个普通钱包 `0x633Ac5e2…ce1`，它可以修改消息配置；两个方向都要求三个 DVN 签字。

**4. 投资人和团队。** 截至 2026-11-14，这部分的锁仓地址尚未公布。在 Rayls 区块浏览器搜索 `RlsTokenLock`，只有 Parfin 这一个合约。

**5. 三天的记录。** 九次读数：锁仓余额、时间表、所有者和管理员都没变；九次完整的权限读数里 RLS 的权限也没变（2026-11-11 16:18 UTC 的第一次查的账户较少）。透明度页面的流通量在 2026-11-11 16:24 到 11-12 00:59 UTC 之间正好增加了 50,000,000 枚，本文没有追查原因。

### 链上读取 vs. 推断

直接读取：上面所有余额、日期、权限、转账和模拟结果。推断或未知：钥匙在谁手里；有没有链下协议约束这些币；投资人和团队的部分是否在别处锁定。模拟只说明一个账户"能做什么"，不代表任何人"打算做什么"。

### 来源

见英文部分。
