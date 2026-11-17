# TokenOne debentures and RWA vaults: what can an investor verify on-chain?

[English](#english) · [中文](#中文)

## English

### Question and scope

Question: **After a real-world asset is tokenised, what can an investor actually verify on a public chain?**

This folder contains a read-only, reproducible audit of three TokenOne debenture tokens and four `RwaVaultV3` contracts on the Rayls Public Chain. It separates three kinds of statement:

1. State and transactions that the public chain can establish directly.
2. External-asset values reported to a vault by an account with `ORACLE_ROLE`.
3. Legal and economic facts that require off-chain records, including the underlying receivables, use of proceeds, beneficial ownership and solvency.

The chosen publication snapshot is **2026-11-17 09:23 UTC, Rayls block 14,661,584**. Live values can change after that block.

### Reproduce

Requirements: Python 3, public network access, and `pycryptodome` for Keccak-256. No wallet, private key, API key or transaction signing is used.

To validate the included publication evidence offline, run from the repository root:

```bash
python3 -m pip install pycryptodome
python3 2026-11-tokenone/build_data.py
python3 2026-11-tokenone/monitor_report.py
```

To query current public state without overwriting the article snapshot:

```bash
export RAYLS_AUDIT_OUT=/tmp/rayls-tokenone-live
python3 2026-11-tokenone/tokenone.py
python3 2026-11-tokenone/vaults_audit.py
python3 2026-11-tokenone/cvm_registry.py
python3 2026-11-tokenone/monitor_report.py
```

The three collection scripts query the official public RPC, the public explorer API and the CVM public registry application. `build_data.py` is offline and deliberately requires the fixed publication block, run time and record counts to match. `monitor_report.py` accepts a new live output directory, records changes against the publication snapshot and leaves `data.json` unchanged.

`tokenone.py` also performs `eth_call` simulations. An `eth_call` is a read-only local execution against current contract state. It does not sign or broadcast a transaction, spend gas or change the chain. A successful simulation describes a contract capability under the simulated caller and state, not a real action or intent.

The Chinese article, X thread and submission description are included in this folder. To regenerate the two branded images, install `cairosvg`, `pillow` and `numpy`, then point the script to the contributor's `rayls-rail-quest` brand helper and the untouched official logo:

```bash
BRANDKIT_DIR=/path/to/rayls-rail-quest/scripts \
RAYLS_LOGO=/path/to/rayls-rail-quest/assets/logo.png \
python3 2026-11-tokenone/images/make_images.py
```

The image script reads the same fixed `data.json` as the article. It does not query live state. The checked local PNGs have SHA-256 `fa2d42e8e43826572635330fdbc8552dd2adec52a6b7110717bfca28ef763e27` for `cover.png` and `624a39ea580a8310692ae9bf1d53953addaf43b51e638d140b9e309623c48883` for `body.png`. Their remote binary upload is pending because the current GitHub connector exposes only UTF-8 text writes; Base64 text must not be committed under a `.png` name.

### Contracts

| Item | Address |
|---|---|
| NF01 | `0x36f480c489f4cf6aacf91c7605504a840060e376` |
| NF02 | `0x424cdecec00bfe64be85f2d53a3e49ee28d05f05` |
| NF03 | `0x6a05c0a11aae5366f0a2520695b516ff6372f26c` |
| AMC01 vault | `0x2bdbd4001eaf67077105b388a5cf2df26c65f1b7` |
| GIRU01 vault | `0x84035676fa725c25346f91e17e4a9f1b41ab1f4f` |
| TKONE02 vault | `0x870c2c4cfaf895f55163385813164e5808ae7029` |
| TKONE01 vault | `0x8fff24202c1360324571df9ca8aff5137a963492` |
| BRLT proxy | `0xe14c117ea3eba1728cc8003590c04eb641f1e268` |
| VaultSeed proxy | `0x5B9565e27F5d50B14D3f660799f87e829A53fab2` |

VaultSeed is a separate launch-deposit contract, not one of the four `RwaVaultV3` contracts.

### Debenture results at the snapshot

| Token | Supply | Current holder addresses | Explorer transfers after mint | Compliance module |
|---|---:|---:|---:|---|
| NF01 | 10,000,000 | 1 | 0 | Configured |
| NF02 | 20,000,000 | 1 | 0 | Zero address |
| NF03 | 5,000,000 | 1 | 0 | Zero address |

The supplies sum to 35,000,000 tokens. For each token, current RPC balances of all discovered holders sum to `totalSupply`. The explorer's complete event and contract-transaction history contains the mint but no later token transfer. This does **not** establish the number of investors or their beneficial ownership.

For NF01, the configured compliance module rejects a simulated transfer from the holder to an unregistered address. For NF02 and NF03, `compliance()` is the zero address and the same simulation returns success. Simulated issuer minting and enforcer forced transfer to that address also succeed for NF02 and NF03. These are observations of the current configuration, not allegations about why it was chosen.

The same plain account, `0x14f918b1739e325ef588b725f1ee63c6215db335`, held `DEFAULT_ADMIN`, `ISSUER`, `ENFORCER` and `PAUSER` on all three tokens at the snapshot.

**RPC limitation:** the official RPC returned zero `Transfer` logs for each token even though the explorer has one mint log for each. The script records this disagreement explicitly. RPC log search is diagnostic and is not used as evidence that transfers are absent. The absence statement rests on full explorer event history, full transactions to the token contract and current RPC balances.

### Vault accounting results at the snapshot

The verified `RwaVaultV3` source computes:

```solidity
totalAssets = IERC20(asset()).balanceOf(address(this)) + deployedCapital
```

`idleAssets()` is the token balance held by the vault contract. `deployedCapital` is an external-asset value reported through the vault's accounting functions. The contract source itself distinguishes the directly verifiable balance from the value reported by `ORACLE_ROLE`.

| Vault | Asset | idleAssets | deployedCapital | totalAssets |
|---|---|---:|---:|---:|
| AMC01 | BRLT | 1,000 | 209,638.82445 | 210,638.82445 |
| GIRU01 | BRLT | 0 | 1,000.76182 | 1,000.76182 |
| TKONE02 | BRL1.p | 10.018367822485536403 | 0.010765422285485408 | 10.029133244771021811 |
| TKONE01 | BRLT | 45,000 | 124,424.349101 | 169,424.349101 |

All four formulas match exactly. Every `idleAssets()` value also equals an independent RPC `balanceOf(vault)` read.

The audit paginated through all 343 explorer logs for the four vaults. It decoded and published all 164 `CapitalWithdrawn`, `CapitalReturned` and `DeployedCapitalReported` records in `data/vault_capital_events.csv`. It then read every asset transfer for each manager address and checked withdrawals, returns, mints, burns and current balances. All 21 reconciliation assertions pass.

For the three BRLT vaults, the separate historical totals are:

- `CapitalWithdrawn`: 332,758.784998 BRLT.
- `CapitalReturned`: 31 BRLT.
- Manager-address burns: 332,738.78 BRLT.

These totals are not a residual-balance equation. In particular, AMC01 returned 11 BRLT that had first been newly minted to its manager. Each manager is therefore reconciled separately.

TKONE01 provides a compact worked example:

```text
withdrawn 123,677.784998 BRLT
= burned 123,657.78 + returned 20 + manager balance 0.004998
```

A burn proves that BRLT left on-chain circulation. It does not identify what was purchased off-chain, which receivable was acquired, or how legal settlement occurred. The three debenture contracts have only their mint transfers in the explorer history, so their token histories cannot by themselves pair vault withdrawals with a particular debenture purchase.

The verified source restricts `reportDeployedCapital()` in two relevant ways: it cannot create a deployed position when the previous value is zero, and a non-zero `maxReportDeviationBps` limits the change from the previous report. All four vaults had a 1,000 basis-point deviation limit and an 86,400-second maximum report age at the snapshot. These are accounting controls, not independent proof of the external asset.

### Launch-deposit aggregates and privacy

VaultSeed held 255,276.47899 BRL1.p at the snapshot, with 12 incoming transfers, zero outgoing transfers and eight distinct incoming sources. Its balance equals incoming minus outgoing transfers. The latest `LockEndSet` value corresponds to 2026-11-19 23:59:59 UTC.

Only contract-level aggregates are published for VaultSeed. Depositor addresses and per-depositor amounts are intentionally excluded from the generated output.

### CVM registry scope

The CVM public crowdfunding-registry application returned TokenOne LTDA, CNPJ 37.728.588/0001-04, status `Em Funcionamento Normal`, CVM code 1244, registration date 2026-02-04, process 19957.017805/2025-88.

This confirms the platform's registry entry only. It is not a CVM review or endorsement of NF01, NF02 or NF03. TokenOne's own FAQ states that offerings use a registration exemption and that CVM does not review each offering in advance. A missing standalone CVM entry for one of these offerings must not be presented as an anomaly on that basis alone.

### Files

| Path | Contents |
|---|---|
| `article.md` | Original Chinese Binance Square article with the fixed evidence permalink |
| `x_thread.md` | Eight-post Chinese X thread with explicit image and publication-link placeholders |
| `submission.md` | English quest submission description and its Chinese meaning |
| `images/make_images.py` | Data-driven generator for the horizontal cover and vertical in-body image |
| `images/cover.png` and `images/body.png` | Final 2x Rayls-brand images generated and visually checked locally; remote binary upload pending, with SHA-256 values recorded above |
| `tokenone.py` | Supplies, holders, roles, compliance, simulations, explorer history and RPC-log diagnostic |
| `vaults_audit.py` | Full vault event pagination, capital events, current state, manager-flow reconciliation and assertions |
| `cvm_registry.py` | CVM public platform-registry query |
| `build_data.py` | Offline publication-data builder and fixed-snapshot consistency checks |
| `monitor_report.py` | Live-state change report and accounting checks without overwriting the article snapshot |
| `tokenone-monitor.pending.yml` | Prepared but inactive expanded Actions workflow |
| `data/monitor_latest.json` and `data/monitor_history.jsonl` | Privacy-preserving monitor state and append-only summary history |
| `data.json` | Single source for the article, images and X thread |
| `data/tokens.json` | Debenture snapshot |
| `data/vaults.json` | Vault, BRLT and VaultSeed snapshot with 21 checks |
| `data/vault_capital_events.csv` | Every decoded capital event behind the aggregates |
| `data/manager_asset_transfers.csv` | All 38 institutional manager asset transfers behind the burn, return, mint and balance checks |
| `data/cvm.json` | Normalised CVM result |
| `raw/audit/` | Generated locally by the audit script, but not committed: complete vault event payloads can contain depositor addresses. The two public CSVs above preserve every record used in the capital and institutional-manager calculations; raw responses can be fetched again with the script |
| `raw/cvm/` | Raw CVM registry response |
| `runs/` | Selected dated stdout logs for the publication snapshot |

The four `contractURI` values are saved. Their IPFS metadata could not be retrieved in this run, so this audit makes no claim about its contents.

### Monitoring

At this evidence commit, the existing scheduled workflow still covers `tokenone.py` only. An expanded monitor is prepared in `tokenone-monitor.pending.yml`, but it is not active while workflow-file authorization and an Actions validation run are pending. The publication logs cited here are manual public runs, not a claim that the expanded monitor has already run. The pending design keeps raw responses outside the repository, records debenture and vault outcomes separately, and fails the run if any required check fails.

### Evidence boundary

This audit verifies public contract state and transaction accounting. It does not establish the existence, ownership, valuation, registration or collectability of specific off-chain receivables. It does not prove BRLT's real-world reserves, individual investors' platform balances, or an issuer's solvency. Nothing here is investment advice.

## 中文

### 问题与范围

问题：**RWA 上链后，投资人到底能在链上核对什么？**

本目录是一套只读、可复现的核查，对象是 Rayls 公链上的三只 TokenOne 债券代币和四个 `RwaVaultV3` 合约。核查把陈述分成三层：公开链能直接证明的状态与交易；`ORACLE_ROLE` 向金库报告的链外资产数值；必须依靠链下文件确认的应收账款、资金用途、实际投资人和偿付能力。

文章采用的快照是 **2026-11-17 09:23 UTC，Rayls 区块 14,661,584**。之后的实时数值可能变化。

### 复现方法

只需要 Python 3、公共网络和用于 Keccak-256 的 `pycryptodome`。不需要钱包、私钥、API 密钥，也不会签名或广播交易。

在仓库根目录离线校验本提交内的发布证据：

```bash
python3 -m pip install pycryptodome
python3 2026-11-tokenone/build_data.py
python3 2026-11-tokenone/monitor_report.py
```

如果要读取当前公开状态，又不覆盖文章快照：

```bash
export RAYLS_AUDIT_OUT=/tmp/rayls-tokenone-live
python3 2026-11-tokenone/tokenone.py
python3 2026-11-tokenone/vaults_audit.py
python3 2026-11-tokenone/cvm_registry.py
python3 2026-11-tokenone/monitor_report.py
```

前三个采集脚本读取公共 RPC、公共浏览器接口和 CVM 公开注册查询应用。`build_data.py` 不访问网络，它会有意要求固定发布区块、运行时间和记录数完全匹配。`monitor_report.py` 接受新的实时输出目录，记录相对发布快照的变化，不改动文章的 `data.json`。

`tokenone.py` 中的模拟全部是 `eth_call`。它只针对当前合约状态做只读执行，不会上链。模拟成功表示在指定调用者和当前状态下合约允许这条调用路径，不表示有人真的执行过，也不表示任何主观意图。

中文文章、X 推文串和英文提交说明都在本目录。重新生成两张品牌图还需安装 `cairosvg`、`pillow` 和 `numpy`，并把环境变量指向贡献者的 `rayls-rail-quest` 品牌工具与未修改的官方 Logo：

```bash
BRANDKIT_DIR=/path/to/rayls-rail-quest/scripts \
RAYLS_LOGO=/path/to/rayls-rail-quest/assets/logo.png \
python3 2026-11-tokenone/images/make_images.py
```

图片脚本与文章读取同一个固定 `data.json`，不会查询实时状态。已检查的本地 PNG 校验值为：`cover.png` 的 SHA-256 是 `fa2d42e8e43826572635330fdbc8552dd2adec52a6b7110717bfca28ef763e27`，`body.png` 是 `624a39ea580a8310692ae9bf1d53953addaf43b51e638d140b9e309623c48883`。当前 GitHub 连接器只提供 UTF-8 文本写入，因此远端二进制上传仍待完成，不能把 Base64 文本直接命名为 `.png` 提交。

### 三只债券的结果

| 代币 | 供应量 | 当前持有地址数 | 铸造后的浏览器转账记录 | 合规模块 |
|---|---:|---:|---:|---|
| NF01 | 10,000,000 | 1 | 0 | 已设置 |
| NF02 | 20,000,000 | 1 | 0 | 零地址 |
| NF03 | 5,000,000 | 1 | 0 | 零地址 |

三只代币合计 35,000,000。每只代币所有已发现持有地址的 RPC 当前余额之和都等于 `totalSupply`。浏览器全量事件与合约交易记录中只有铸造，没有之后的代币转账。这不能用来确定投资人数或实际受益所有人。

NF01 的合规模块会拒绝持有地址向未登记地址的模拟转账。NF02 和 NF03 的 `compliance()` 是零地址，同样的模拟可以成功，发行方模拟增发与执行方模拟强制转移也能成功。这里只记录当前配置与合约能力，不推测这样配置的原因。

快照时，三只代币的 `DEFAULT_ADMIN`、`ISSUER`、`ENFORCER` 和 `PAUSER` 都由同一个普通账户 `0x14f918b1739e325ef588b725f1ee63c6215db335` 持有。

**RPC 限制：**官方 RPC 对三只代币都返回 0 条 `Transfer` 日志，但浏览器各有 1 条铸造日志。脚本明确保存这项矛盾。RPC 日志搜索只作为诊断，不能用来证明没有转账。没有后续转账的判断来自浏览器全量事件、全量合约交易和 RPC 当前余额的交叉核对。

### 四个金库的结果

已验证源码中的计算公式是：

```solidity
totalAssets = IERC20(asset()).balanceOf(address(this)) + deployedCapital
```

`idleAssets()` 是金库合约实际持有的代币余额。`deployedCapital` 是通过金库记账函数报告的外部资产数值。合约源码也明确区分了链上可验证余额和 `ORACLE_ROLE` 报告值。

| 金库 | 资产 | idleAssets | deployedCapital | totalAssets |
|---|---|---:|---:|---:|
| AMC01 | BRLT | 1,000 | 209,638.82445 | 210,638.82445 |
| GIRU01 | BRLT | 0 | 1,000.76182 | 1,000.76182 |
| TKONE02 | BRL1.p | 10.018367822485536403 | 0.010765422285485408 | 10.029133244771021811 |
| TKONE01 | BRLT | 45,000 | 124,424.349101 | 169,424.349101 |

四个公式全部精确成立，每个 `idleAssets()` 也都等于独立读取的 RPC `balanceOf(vault)`。

脚本分页读取了四个金库全部 343 条浏览器事件，把其中 164 条 `CapitalWithdrawn`、`CapitalReturned` 和 `DeployedCapitalReported` 逐笔解码到 `data/vault_capital_events.csv`。随后读取每个经理地址的全量资产转账，核对提取、归还、铸造、销毁和当前余额。21 项对账断言全部通过。

三个 BRLT 金库的历史流量分别为：提取 332,758.784998 BRLT，归还 31 BRLT，经理地址销毁 332,738.78 BRLT。这三项不能直接相减当作剩余余额，因为 AMC01 归还的 11 BRLT 是先新铸给经理再归还的。脚本按每个经理地址分别对账。

TKONE01 的完整等式是：

```text
提取 123,677.784998 BRLT
= 销毁 123,657.78 + 归还 20 + 经理余额 0.004998
```

销毁只能证明 BRLT 离开链上流通，不能说明链下买了什么、对应哪笔应收账款，或者法律结算如何完成。三只债券合约在浏览器历史中各自只有铸造转账，所以仅凭这些代币历史，无法把金库提款与某只债券购买一一配对。

已验证源码对 `reportDeployedCapital()` 有两项相关限制：之前没有已投出头寸时不能凭报告创造头寸；`maxReportDeviationBps` 非零时，新报告相对上次报告的变化不能超过上限。快照时四个金库的报告偏离上限都是 1,000 个基点，最大报告年龄都是 86,400 秒。这些属于会计控制，不是外部资产的独立证明。

### 首发存款与隐私

VaultSeed 是独立首发存款合约，不属于上述四个 `RwaVaultV3`。快照时余额为 255,276.47899 BRL1.p，有 12 笔转入、0 笔转出和 8 个不同转入来源，余额与转入减转出一致。最新 `LockEndSet` 对应 2026-11-19 23:59:59 UTC。

VaultSeed 只发布合约级聚合数据，生成结果会主动排除存款人地址和逐人金额。

### CVM 核验边界

CVM 公开众筹注册查询返回 TokenOne LTDA，CNPJ 37.728.588/0001-04，状态为 `Em Funcionamento Normal`，CVM 编号 1244，注册日期 2026-02-04，进程号 19957.017805/2025-88。

这只能证明平台注册记录，不是 CVM 对 NF01、NF02 或 NF03 的审核或背书。TokenOne 自己的常见问题说明相关发行采用注册豁免，CVM 不逐单预审。因此，不能仅因没有找到某次发行的独立 CVM 登记就把它写成异常。

### 文件与监控

文件用途见上方英文表格。四个 `contractURI` 已保存，但本次没有成功读取 IPFS 元数据，因此不对元数据内容作任何断言。

在这个证据提交中，现有定时工作流仍只运行 `tokenone.py`。扩展版本已准备在 `tokenone-monitor.pending.yml`，但工作流文件授权和 Actions 实际验证尚未完成，因此它没有激活。这里引用的发布日志是公开手动运行结果，不冒充扩展监控已经上线。待定版本会把原始响应留在仓库外，分别记录债券与金库任务结果，任一必要检查失败都会让整次运行失败。

### 证据边界

本核查证明的是公开合约状态与交易记账，不证明特定链下应收账款是否存在、归谁所有、如何估值、在哪里登记或能否收回，也不证明 BRLT 的现实储备、平台内个人份额或发行人的偿付能力。本文与代码均不构成投资建议。
