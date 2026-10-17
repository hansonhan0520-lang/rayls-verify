# BRL1.p backing check · BRL1.p 背书核查

[English](#english) · [中文](#中文)

---

## English

**Question:** How can an ordinary user verify a bridged stablecoin's "1:1 backing"?

**Case:** BRL1.p on the Rayls Public Chain, a LayerZero lock-and-mint bridge of BRL1, a Brazilian real stablecoin on Polygon.

"1:1 backing" is really three separate claims. `verify-brl1p.js` checks the first two on-chain. For the third, it reads only what the chain can show.

| Layer | Question | Where the answer lives |
|---|---|---|
| 1 | Does the lockbox hold at least as much BRL1 as there is BRL1.p? | On-chain, computable |
| 2 | Who can mint extra BRL1.p, or change the rules? | On-chain, readable, rests on key custody |
| 3 | Is BRL1 itself backed by reais? | Off-chain, issuer report |

### Run it

Node 18 or later:

```
node verify-brl1p.js
```

Or open any https page in a browser, press F12, paste the whole file into the console and press Enter.

### Contracts

| | Address |
|---|---|
| BRL1 (Polygon) | `0x5C067C80C00eCd2345b05E83A3e758eF799C40B5` |
| Bridge lockbox (Polygon, LayerZero OFTAdapter) | `0x3Ea6BaC7d4138BcC126D0F17aE10122B3620abA6` |
| BRL1.p (Rayls, ERC1967 proxy) | `0xA069d3798FEAb32994aC5D98A9F011DA6024f334` |
| BRL1.p implementation | `0xCAcBa996CA4c2AC37144BA30BFEBC5f7cDBD36D7` |
| RaylsMintBurnOFTAdapter (Rayls) | `0xE56dDf65E311CddB71f69c0aC4D27E58B239D69a` |

### Recorded run: 2026-10-17 07:21 UTC

Full output: [`evidence/run_2026-10-17T0721Z.log`](evidence/run_2026-10-17T0721Z.log). Script SHA-256 `4e79b3bb565b0cab2ed542a4a2205cbf9d546a96977450737c20ae95bacb3b58`. The run was done in a browser console on dapp.rayls.com. Polygon block 95677540, Rayls block 12668378.

- **Stock.** The lockbox held 250,013.482911 BRL1. BRL1.p total supply was 250,013.482911. Difference 0. Four reads between 07:04 and 07:21 UTC returned the same value.
- **Flows since deployment.** 13 locks totalling 259,589.937257 matched 13 mints totalling 259,589.937257. 2 unlocks totalling 9,576.454346 matched 2 burns totalling 9,576.454346.
- **Latency.** Polygon to Rayls took 248 to 274 s across all 13 transfers, median 265 s. Rayls to Polygon took 57 s and 63 s. Transfers were paired by equal amount, equal address and time order, not by decoding LayerZero message GUIDs.
- **Wiring.** Each bridge contract's peer is the other one.
- **Roles.** `MINTER_ROLE` and `BURNER_ROLE` were granted only to the Rayls adapter. There were 5 `RoleGranted` events and 0 revocations. `DEFAULT_ADMIN_ROLE`, `PAUSER_ROLE` and `UPGRADER_ROLE` on BRL1.p, ownership of both bridge contracts, and the LayerZero delegate on both endpoints were all held by `0x633Ac5e2315b973417e8caa6B3Ad2162e0461ce1`. That address has no contract code on either chain.
- **Messaging.** 3 required DVNs and 0 optional ones in each direction: LayerZero Labs, Nethermind and Canary. Messages wait 120 confirmations on Polygon and 10 on Rayls.
- **Issuer layer.** BRL1 was not paused. Its DenyList access registry gave the lockbox access. BRL1 supply on Polygon was 16,575,367.54, so the lockbox held about 1.51%.

### Layer 3: the BRL1 reserve report

The report is dated 2026-10-01. It states 17,381,384.54 BRL1 in circulation at Polygon block 94777137 against R$19,354,372 of reserves, a collateralization of 111.35%.

Reading `totalSupply` at that block through an archive RPC returned exactly 17,381,384.54. The block timestamp is 16:07:26 UTC, one second after the report's 16:07:25.

The report says it was prepared internally and "has not yet been audited by an independent entity". The Rayls BRL1.p documentation describes the consortium's reports as audited.

### Notes from running it

- The Polygon Blockscout "Tokens" panel for the lockbox showed 0 tokens at 07:11 UTC. Reading `balanceOf` a minute later returned 250,013.482911. Read the contract, not the explorer's balance panel ([screenshot](evidence/2026-10-17_0711UTC_polygon_blockscout_tokens_panel_0.jpg)).
- On 2026-10-17 the public Rayls RPC returned no logs or receipts for the deployment blocks around 12437224, while explorer.rayls.com had them. So the script reads Rayls-side event history from the explorer API, and current state from the RPC.
- The verified Polygon lockbox source is named `WDATAAdapter`, and its comments refer to another token. The file only defines a constructor on top of LayerZero's `OFTAdapter`. Its constructor arguments and the on-chain `token()` value both point to BRL1. A reused template name is my inference. I found nothing showing it changes behaviour.

### Read on-chain vs. inferred

Read directly: every balance, flow, role, peer, DVN and confirmation figure above, plus the historical `totalSupply`.

Inference or open question: the template-reuse explanation, and whether admin roles will move to a multisig or timelock. LayerZero's integration checklist recommends a multisig for both owner and delegate.

### Evidence

| File | What it shows |
|---|---|
| `run_2026-10-17T0721Z.log` | Full script output from the recorded run |
| `terminal_run_2026-10-17T0721Z.png` | The same log rendered as an image. This is a rendering, not a screen capture |
| `2026-10-17_0712UTC_polygon_balanceOf_vault.jpg` | Blockscout read of `balanceOf(lockbox)` on BRL1 |
| `2026-10-17_0713UTC_rayls_totalSupply_BRL1p.jpg` | Rayls explorer read of `totalSupply()` on BRL1.p |
| `2026-10-17_0710UTC_rayls_token_page.jpg` | BRL1.p token page on explorer.rayls.com |
| `2026-10-17_0711UTC_polygon_blockscout_tokens_panel_0.jpg` | Explorer balance panel showing 0 while the contract held 250k |

### Sources

- Rayls docs, Get BRL1.p, read 2026-10-17: https://docs.rayls.com/docs/get-brl1p
- Rayls blog, launch deposits, 2026-10-15: https://www.rayls.com/blog/first-vault-on-rayls-launch-deposits-open
- BRL1 Proof of Reserves, reference date 2026-10-01: https://drive.google.com/file/d/1BuRUC6u3UTzf17kOChhKby_L9hE5IU73/view
- LayerZero integration checklist: https://docs.layerzero.network/v2/tools/integration-checklist
- LayerZero DVN registry: https://metadata.layerzero-api.com/v1/metadata/dvns

---

## 中文

**问题：** 跨链桥稳定币说"1:1 背书"，普通人怎么自己验证？

**案例：** Rayls 公链上的 BRL1.p。它是巴西雷亚尔稳定币 BRL1 通过 LayerZero"锁定再铸造"模式从 Polygon 桥过来的版本。

"1:1 背书"其实是三件事。`verify-brl1p.js` 在链上检查前两件；第三件只读取链上能看到的那部分。

| 层 | 问题 | 答案在哪里 |
|---|---|---|
| 1 | 金库里锁的 BRL1 是否不少于 BRL1.p 流通量？ | 链上，可以直接算 |
| 2 | 谁能多印 BRL1.p，谁能改规则？ | 链上可读，依赖钥匙保管 |
| 3 | BRL1 本身有没有雷亚尔储备？ | 链下，看发行方报告 |

### 运行方法

用 Node 18 或更高版本：

```
node verify-brl1p.js
```

也可以在浏览器里打开任意 https 网页，按 F12，把整个文件粘贴进控制台，再按回车。

### 合约地址

| | 地址 |
|---|---|
| BRL1（Polygon） | `0x5C067C80C00eCd2345b05E83A3e758eF799C40B5` |
| 桥金库（Polygon，LayerZero OFTAdapter） | `0x3Ea6BaC7d4138BcC126D0F17aE10122B3620abA6` |
| BRL1.p（Rayls，ERC1967 代理合约） | `0xA069d3798FEAb32994aC5D98A9F011DA6024f334` |
| BRL1.p 实现合约 | `0xCAcBa996CA4c2AC37144BA30BFEBC5f7cDBD36D7` |
| RaylsMintBurnOFTAdapter（Rayls） | `0xE56dDf65E311CddB71f69c0aC4D27E58B239D69a` |

### 记录在案的运行：2026-10-17 07:21 UTC

完整输出见 [`evidence/run_2026-10-17T0721Z.log`](evidence/run_2026-10-17T0721Z.log)。脚本 SHA-256 为 `4e79b3bb565b0cab2ed542a4a2205cbf9d546a96977450737c20ae95bacb3b58`，在 dapp.rayls.com 页面的浏览器控制台中运行。Polygon 区块 95677540，Rayls 区块 12668378。

- **余额：** 金库锁有 250,013.482911 枚 BRL1，BRL1.p 总供应量为 250,013.482911 枚，差额为 0。07:04 到 07:21 UTC 之间读了四次，数值相同。
- **部署以来的流水：** 锁入 13 笔，合计 259,589.937257 枚，对应铸造 13 笔，合计 259,589.937257 枚。放出 2 笔，合计 9,576.454346 枚，对应销毁 2 笔，合计 9,576.454346 枚。
- **跨链用时：** 从 Polygon 到 Rayls，全部 13 笔用时 248 到 274 秒，中位数 265 秒。从 Rayls 到 Polygon 的两笔分别用了 57 秒和 63 秒。这里是按"金额相同、地址相同、时间先后"配对的，没有解码 LayerZero 的消息编号。
- **互指关系：** 两边的桥合约都把对方登记为对端。
- **权限：** `MINTER_ROLE` 和 `BURNER_ROLE` 只授予过 Rayls 上的桥合约，共有 5 条 `RoleGranted` 事件，没有撤销记录。BRL1.p 的 `DEFAULT_ADMIN_ROLE`、`PAUSER_ROLE` 和 `UPGRADER_ROLE`，两边桥合约的 owner，以及两条链上 LayerZero 端点的代理人（delegate），都在 `0x633Ac5e2315b973417e8caa6B3Ad2162e0461ce1` 这个地址上。这个地址在两条链上都没有合约代码。
- **跨链消息：** 每个方向都要求 3 个必需 DVN，没有可选 DVN，分别是 LayerZero Labs、Nethermind 和 Canary。Polygon 发出的消息要等 120 个区块确认，Rayls 发出的要等 10 个。
- **发行方层面：** BRL1 没有暂停。它的 DenyList 访问控制合约对桥金库是允许状态。Polygon 上 BRL1 总量为 16,575,367.54 枚，金库约占 1.51%。

### 第三层：BRL1 的储备报告

报告的参考日是 2026-10-01。报告写的是：在 Polygon 第 94777137 区块，BRL1 流通量为 17,381,384.54 枚，储备为 R$19,354,372，抵押率 111.35%。

我用存档节点读了该区块的 `totalSupply`，结果正好是 17,381,384.54 枚。区块时间为 16:07:26 UTC，比报告写的 16:07:25 晚一秒。

报告自己写明它由内部编制，"has not yet been audited by an independent entity"（尚未经过独立机构审计）。而 Rayls 的 BRL1.p 文档把联盟发布的储备报告描述为经过审计的。

### 运行时发现的情况

- 07:11 UTC 时，Polygon Blockscout 上金库地址的"Tokens"栏显示 0 个代币；一分钟后直接读 `balanceOf`，结果是 250,013.482911 枚。所以要读合约，不要看浏览器的余额栏（[截图](evidence/2026-10-17_0711UTC_polygon_blockscout_tokens_panel_0.jpg)）。
- 2026-10-17 当天，Rayls 官方公共 RPC 对 12437224 附近的部署区块不返回事件日志和交易回执，而 explorer.rayls.com 上有这些记录。所以脚本里 Rayls 一侧的历史事件改从浏览器接口读取，当前状态仍然从 RPC 读取。
- Polygon 金库在浏览器上验证的源码名为 `WDATAAdapter`，注释里写的是另一个代币。这个文件只在 LayerZero 的 `OFTAdapter` 之上写了一个构造函数；它的构造参数和链上 `token()` 返回值都指向 BRL1。说它是复用模板没改名，是我的推断；我没有找到它影响功能的证据。

### 链上读取与推断的区分

直接从链上读出的：上面所有余额、流水、权限、对端、DVN 和确认数，以及历史区块的 `totalSupply`。

属于推断或待观察的：复用模板的解释，以及管理权限今后会不会迁移到多签或时间锁。LayerZero 集成检查清单建议 owner 和 delegate 都使用多签。

### 证据文件

| 文件 | 内容 |
|---|---|
| `run_2026-10-17T0721Z.log` | 记录在案那次运行的完整输出 |
| `terminal_run_2026-10-17T0721Z.png` | 把同一份日志渲染成的图片，不是屏幕截图 |
| `2026-10-17_0712UTC_polygon_balanceOf_vault.jpg` | 在 Blockscout 上读取 BRL1 的 `balanceOf(金库)` |
| `2026-10-17_0713UTC_rayls_totalSupply_BRL1p.jpg` | 在 Rayls 浏览器上读取 BRL1.p 的 `totalSupply()` |
| `2026-10-17_0710UTC_rayls_token_page.jpg` | explorer.rayls.com 上的 BRL1.p 代币页面 |
| `2026-10-17_0711UTC_polygon_blockscout_tokens_panel_0.jpg` | 浏览器余额栏显示 0，而合约里实际有 25 万多枚 |

### 来源

- Rayls 文档 Get BRL1.p，读取于 2026-10-17：https://docs.rayls.com/docs/get-brl1p
- Rayls 博客，启动存款公告，2026-10-15：https://www.rayls.com/blog/first-vault-on-rayls-launch-deposits-open
- BRL1 储备报告，参考日 2026-10-01：https://drive.google.com/file/d/1BuRUC6u3UTzf17kOChhKby_L9hE5IU73/view
- LayerZero 集成检查清单：https://docs.layerzero.network/v2/tools/integration-checklist
- LayerZero DVN 公开名录：https://metadata.layerzero-api.com/v1/metadata/dvns

本文件内容不构成投资建议。
