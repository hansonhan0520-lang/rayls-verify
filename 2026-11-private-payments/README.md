# How can I make private stablecoin payments that regulators can still audit? · 隐私稳定币支付，怎样做到监管仍能审计？

[English](#english) · [中文](#中文)

---

## English
Use a payment system that hides each payment from the public but gives a named auditor a key that can read it, and nothing more. On the Rayls Public Chain, Enygma Public does this today as a testnet pilot: a shielded USDr payment shows no payer, payee or amount on the explorer, while the deployment's auditor holds an encrypted copy of every account's view key and can read every payment, but cannot move or freeze funds.

*Written 25 November 2026. Enygma Public is a testnet pilot running on test tokens with no value.*

### What "private but auditable" has to mean

A stablecoin payment on a normal public chain is visible to everyone: sender, receiver, amount, forever. That is a problem for payroll, supplier payments or treasury moves, where competitors and strangers should not see who paid whom.

Making payments invisible is not enough for a regulated business, though. A compliance team, an auditor or a supervisor still needs to read the full record, and the person holding that record should not be able to spend anyone's money. So the question to ask of any system is: who can see a payment, who decides that, and what else can they do with that access.

### How the projects people already know answer it

| | Where payments settle | Who decides what an auditor sees | Status |
|---|---|---|---|
| [Zcash](https://zechub.wiki/zcash-tech/viewing-keys) | Public chain, shielded pool | The account owner, by sharing a viewing key. The key reads but cannot spend | Live |
| [Canton Network](https://docs.canton.network/overview/learn/privacy-model) | Each party's validator holds only its own data | The contract design: a regulator is added as an observer to the contracts it should see | Live |
| [ZKsync Prividium](https://zksync.io/prividium) | A chain run by the institution; only proofs go to Ethereum | The operator, which grants regulators access to what they are authorised to see | Live, vendor-reported bank deployments |
| [Circle Arc Privacy](https://www.arc.io/blog/privacy-with-control-how-arc-can-unlock-onchain-finance) | Arc, opt-in per use | Authorised parties such as compliance teams "can be granted the access they need" | Announced 10 June 2026, design not final |
| [Rayls Enygma Public](https://docs.rayls.com/docs/enygma-public) | Rayls Public Chain, shielded vaults | Built in: every account gives the deployment's auditor a copy of its view key when it registers | Testnet pilot |

Each of these is a fair answer for a different situation. Zcash puts disclosure in the user's hands, which suits individuals but means an auditor only sees what each user chooses to share. Canton and Prividium keep data off any shared public ledger, which suits institutions that run their own infrastructure and transact with known counterparties. Arc's design is still being written.

### Where Rayls fits

Enygma Public sits between these. Payments settle on a public chain that anyone can join, like Zcash, but oversight is not optional, closer to Canton and Prividium. The [Rayls docs](https://docs.rayls.com/docs/enygma-public-who-sees-what) describe the split this way: shielded from the public, not from the auditor.

How it works, in short ([docs](https://docs.rayls.com/docs/how-enygma-public-works)):

- An account holds a shielded balance as encrypted notes in vault contracts. The testnet has a vault for USDr, the Rayls Public Chain's dollar stablecoin used for gas, one for RLS, and a shared vault for any ERC-20.
- A payment is proven with a zero-knowledge proof made in the sender's browser. A relayer run by Rayls submits it from its own address, so the sender's address does not appear.
- At registration, the wallet encrypts a copy of the account's view key to the deployment's auditor key with ML-KEM-768 and stores it in the registry contract. The auditor can decrypt every shielded payment: who paid whom, how much, which token.
- The auditor holds view keys, not spend keys, and no Enygma Public contract can freeze or block funds. One deployment has one auditor key, so a deployment per country keeps each auditor to its own country's activity. On the testnet, Rayls is the auditor.

For banks that run their own ledger inside a Rayls Private Network, the related product is [Enygma Sovereign](https://docs.rayls.com/docs/enygma-privacy-and-auditing). There the reading role belongs to the Private Network operator, usually a central bank, a clearing house or the parent of a banking group, which can read every transfer that crosses the network and cannot sign any of them.

### What I checked myself

All checks are read-only calls to the public testnet explorer and RPC, run on 25 November 2026. The scripts are in this folder (see the table at the end).

**A shielded USDr payment shows nothing about the parties.** Transaction [0x5a84…f450](https://testnet-explorer.rayls.com/tx/0x5a84068136fbc126a59cea8b0dc008ccf95c05de78d906395c3ed1db2190f450) (24 November 2026, 11:07 UTC) is a payment from the USDr vault. Four addresses appear in it, as sender, target or event emitter, and none belongs to a user: the Enygma relayer, Multicall3 (a standard contract the relayer uses to send a payment and its gas fee together), the USDr vault and the shared vault. Its value is 0 USDr and it has no token transfers. What it does publish is one nullifier, two new commitments and two encrypted notes.

**Moving money in or out is public, as the docs say.** For contrast, the unshield [0x74ea…2338](https://testnet-explorer.rayls.com/tx/0x74ea2ef5269beb130229d087b91a2f517815e2b0dd97d0bcf3901da377d12338) (24 November 2026) shows the receiving address and the amount, 0.01 USDr. My own shielded send from the 12 November demo, [0x140e…d36d](https://testnet-explorer.rayls.com/tx/0x140ec97b9c4eda3afa146fd71fcedd40eb036de7b21f1ec6e8aa071c45f4d36d), looks like the payment above: only the relayer and the shared vault appear.

**Every registered account has given the auditor a copy of its view key.** The [registry contract](https://testnet-explorer.rayls.com/address/0xA473291FFb33e2276F364fAE169f03c4406719e9) takes the auditor ciphertexts as part of `register`. I read them for all 319 registered accounts: none is missing, and each ML-KEM part is 1,088 bytes, the size of an ML-KEM-768 ciphertext. The auditor public key is 1,184 bytes, the size of an ML-KEM-768 public key ([sizes](https://openquantumsafe.org/liboqs/algorithms/kem/ml-kem)). Seven accounts hold the auditor role.

**The public sees the pool, not the owners.** The USDr vault held 8,653.77 test USDr at block 25,497,719. Anyone can read that total; nobody outside can tell whose notes make it up.

Limits: I cannot open the auditor view, because Rayls is the testnet auditor, so I checked that the escrowed keys exist and have the right form, not that the auditor decrypts them. The payment I examined was made by another tester; I picked it because it moves USDr. Test tokens have no value.

### Before using this for real money

- Enygma Public is a testnet pilot. The testnet's proving keys come from a single-party setup that the docs call suitable for testing only; production needs a multi-party ceremony.
- Shielding and unshielding show the address, token and amount. Privacy covers payments between shielded balances.
- Who acts as auditor in a production deployment, for example a country's supervisor, is a choice made when the deployment is set up. The docs also note a deployment without an auditor is possible in principle but is not the focus.

What the testnet already shows is the part a compliance officer cares about: the public chain records that a payment happened and that it was valid, while the full record goes to one named auditor who can read it and cannot spend it.

### Sources

- Rayls docs, Enygma Public: https://docs.rayls.com/docs/enygma-public
- Rayls docs, How Enygma Public works: https://docs.rayls.com/docs/how-enygma-public-works
- Rayls docs, Who sees what in Enygma Public: https://docs.rayls.com/docs/enygma-public-who-sees-what
- Rayls docs, Get the USDr gas token: https://docs.rayls.com/docs/get-usdr-gas-token
- Rayls docs, Enygma privacy and auditing (Sovereign): https://docs.rayls.com/docs/enygma-privacy-and-auditing
- Rayls testnet explorer: https://testnet-explorer.rayls.com
- Zcash viewing keys (ZecHub): https://zechub.wiki/zcash-tech/viewing-keys
- Canton Network privacy model: https://docs.canton.network/overview/learn/privacy-model
- ZKsync Prividium: https://zksync.io/prividium
- Arc, Privacy with control (10 June 2026): https://www.arc.io/blog/privacy-with-control-how-arc-can-unlock-onchain-finance
- ML-KEM sizes (Open Quantum Safe): https://openquantumsafe.org/liboqs/algorithms/kem/ml-kem

### Scripts in this folder

| Script | Output | What it answers |
|---|---|---|
| `check_shielded_tx.py <tx> [<tx> ...]` | `data/<tx>.json` | Every address, event and token transfer in a testnet transaction, labelled; run it on a shield, a shielded payment and an unshield to see what each one shows |
| `registry_check.py` | `data/registry_check.json` | For every registered Enygma Public account, whether the auditor's copy of its view key is in the registry, and its size; counts only, no addresses |
| `vault_pools.py` | `data/vault_pools.json` | Which token each Enygma Public vault holds and the pool totals the public can see |
| `images/make_images.py` | `images/pp-cover.png`, `images/pp-body.png` | The two article images, drawn from `data/` |

Everything is read-only: public explorer API and public RPC calls on the Rayls Public Chain testnet (chain ID 7295799). No wallet, no key. Readings were taken on 2026-11-25 between 15:33 and 15:36 UTC. `images/explorer-shielded-usdr-payment.png` is a screenshot of the explorer page for the payment examined.

---

## 中文

### 隐私稳定币支付，怎样做到监管仍能审计？
做法是用这样一种支付系统：每笔付款对公众隐藏，但给一个指定的审计方一把能读取它的钥匙，而且只能读、不能动钱。在 Rayls 公链上，Enygma Public 目前以测试网试点的形式做到了这一点：一笔隐私 USDr 付款在区块浏览器上看不到付款人、收款人和金额，而该部署的审计方持有每个账户查看密钥（view key）的加密副本，能读取每一笔付款，但不能转走或冻结任何资金。

*写于 2026 年 11 月 25 日。Enygma Public 是测试网试点，使用的是没有价值的测试代币。*

### "隐私但可审计"到底要满足什么

在普通公链上用稳定币付款，谁付给谁、付了多少，所有人都看得到，而且永久留存。发工资、付供应商货款、调拨资金，这些都不该让竞争对手和陌生人看见。

但对受监管的企业来说，光是"看不见"还不够。合规团队、审计师或监管机构仍然需要读到完整记录，而掌握这份记录的人不应该能动用任何人的钱。所以评估任何一个系统，都要问三件事：谁能看到一笔付款，由谁决定，以及拿到查看权限的人还能做什么。

### 大家熟悉的项目是怎么做的

| | 付款在哪里结算 | 谁决定审计方能看到什么 | 现状 |
|---|---|---|---|
| [Zcash](https://zechub.wiki/zcash-tech/viewing-keys) | 公链上的隐私池 | 账户持有人自己，通过分享查看密钥；这把钥匙只能读、不能花 | 已上线 |
| [Canton Network](https://docs.canton.network/overview/learn/privacy-model) | 每一方的验证节点只保存自己的数据 | 合约设计：把监管方加为相关合约的观察者（observer） | 已上线 |
| [ZKsync Prividium](https://zksync.io/prividium) | 机构自己运营的链，只把证明提交到以太坊 | 运营方，向监管方开放其获授权的内容 | 已上线，银行部署情况由厂商自述 |
| [Circle Arc Privacy](https://www.arc.io/blog/privacy-with-control-how-arc-can-unlock-onchain-finance) | Arc 链，按需开启 | 合规团队等获授权方"可以被授予所需的访问权限" | 2026 年 6 月 10 日公布，设计未定稿 |
| [Rayls Enygma Public](https://docs.rayls.com/docs/enygma-public) | Rayls 公链上的隐私金库 | 内置：每个账户注册时都把查看密钥的副本交给该部署的审计方 | 测试网试点 |

这几种方案各自适合不同的场景。Zcash 把披露权交给用户本人，适合个人，但审计方只能看到每个用户愿意分享的部分。Canton 和 Prividium 不把数据放在共享的公共账本上，适合自建基础设施、和已知对手方交易的机构。Arc 的方案还在设计中。

### Rayls 的位置

Enygma Public 介于两者之间。付款像 Zcash 一样在任何人都能加入的公链上结算，但监督不是可选项，这一点更接近 Canton 和 Prividium。[Rayls 文档](https://docs.rayls.com/docs/enygma-public-who-sees-what)对这种分工的说法是：对公众保密，但对审计方透明。

工作方式简单说（[文档](https://docs.rayls.com/docs/how-enygma-public-works)）：

- 账户的隐私余额以加密"票据"（note）的形式存放在金库合约里。测试网有一个 USDr 金库（USDr 是 Rayls 公链用来付 gas 的美元稳定币）、一个 RLS 金库，以及一个可存放任意 ERC-20 的共享金库。
- 每笔付款由发送方在浏览器里生成零知识证明，再由 Rayls 运营的中继器（relayer）用它自己的地址提交，所以发送方的地址不会出现在链上。
- 注册时，钱包用 ML-KEM-768 把账户查看密钥的一份副本加密给该部署的审计方密钥，存进注册合约。审计方能解密每一笔隐私付款：谁付给谁、多少、什么代币。
- 审计方持有的是查看密钥，不是花费密钥；Enygma Public 也没有任何合约能冻结或拦截资金。一个部署只有一把审计方密钥，按国家分别部署，每个审计方就只能看到本国的活动。测试网上的审计方是 Rayls。

对于在 Rayls 私有网络里运行自有账本的银行，对应的产品是 [Enygma Sovereign](https://docs.rayls.com/docs/enygma-privacy-and-auditing)。在那里读取权限属于私有网络的运营方，通常是央行、清算所或银行集团母公司，它能读取经过网络的每一笔转账，但不能签署其中任何一笔。

### 我自己核实了什么

以下都是对公开测试网浏览器和 RPC 的只读查询，时间是 2026 年 11 月 25 日。脚本就在本文件夹（见文末表格）。

**一笔隐私 USDr 付款，看不出任何当事人。** 交易 [0x5a84…f450](https://testnet-explorer.rayls.com/tx/0x5a84068136fbc126a59cea8b0dc008ccf95c05de78d906395c3ed1db2190f450)（2026 年 11 月 24 日 11:07 UTC）是一笔从 USDr 金库发出的付款。交易里出现的地址一共四个，作为发送方、调用对象或事件发出者，没有一个属于用户：Enygma 中继器、Multicall3（中继器用来把付款和 gas 费一起发送的标准合约）、USDr 金库和共享金库。交易金额是 0 USDr，没有任何代币转账记录。它公开的只有一个作废标记（nullifier）、两个新的承诺值（commitment）和两条加密票据。

**存入和取出是公开的，和文档说的一致。** 作为对照，取出交易 [0x74ea…2338](https://testnet-explorer.rayls.com/tx/0x74ea2ef5269beb130229d087b91a2f517815e2b0dd97d0bcf3901da377d12338)（2026 年 11 月 24 日）能看到收款地址和金额 0.01 USDr。我自己 11 月 12 日在演示里做的一笔隐私转账 [0x140e…d36d](https://testnet-explorer.rayls.com/tx/0x140ec97b9c4eda3afa146fd71fcedd40eb036de7b21f1ec6e8aa071c45f4d36d) 和上面那笔付款一样，只出现中继器和共享金库。

**每个注册账户都把查看密钥的副本交给了审计方。** [注册合约](https://testnet-explorer.rayls.com/address/0xA473291FFb33e2276F364fAE169f03c4406719e9)的 `register` 函数本身就带有审计方密文这两个参数。我读取了全部 319 个注册账户：一个都不缺，每份 ML-KEM 密文都是 1,088 字节，正好是 ML-KEM-768 密文的大小。审计方公钥是 1,184 字节，正好是 ML-KEM-768 公钥的大小（[尺寸对照](https://openquantumsafe.org/liboqs/algorithms/kem/ml-kem)）。持有审计方角色的账户有 7 个。

**公众看得到资金池，看不到是谁的。** 在区块 25,497,719，USDr 金库里共有 8,653.77 枚测试 USDr。任何人都能读到这个总数，但外人分不出其中哪些票据属于谁。

局限：我打不开审计方视图，因为测试网的审计方是 Rayls，所以我核实的是托管密钥存在且格式正确，没有核实审计方实际解密。我检查的那笔付款是另一位测试者做的，选它是因为它转的是 USDr。测试代币没有价值。

### 用于真实资金之前要注意

- Enygma Public 还是测试网试点。测试网的证明密钥来自单方生成（single-party setup），文档说明只适合测试，正式部署需要多方仪式（multi-party ceremony）。
- 存入（shield）和取出（unshield）会公开地址、代币和金额。隐私保护的是隐私余额之间的付款。
- 正式部署里由谁担任审计方，比如某国的监管机构，是在建立部署时决定的。文档也提到理论上可以不设审计方，但那不是现在的方向。

测试网已经展示出合规人员最关心的那部分：公链只记录"一笔付款发生了、而且有效"，完整记录交给一个指定的审计方，它能读，但不能花。

### 来源

- Rayls 文档，Enygma Public：https://docs.rayls.com/docs/enygma-public
- Rayls 文档，Enygma Public 如何运作：https://docs.rayls.com/docs/how-enygma-public-works
- Rayls 文档，Enygma Public 中谁能看到什么：https://docs.rayls.com/docs/enygma-public-who-sees-what
- Rayls 文档，获取 USDr gas 代币：https://docs.rayls.com/docs/get-usdr-gas-token
- Rayls 文档，Enygma 隐私与审计（Sovereign）：https://docs.rayls.com/docs/enygma-privacy-and-auditing
- Rayls 测试网浏览器：https://testnet-explorer.rayls.com
- Zcash 查看密钥（ZecHub）：https://zechub.wiki/zcash-tech/viewing-keys
- Canton Network 隐私模型：https://docs.canton.network/overview/learn/privacy-model
- ZKsync Prividium：https://zksync.io/prividium
- Arc，Privacy with control（2026 年 6 月 10 日）：https://www.arc.io/blog/privacy-with-control-how-arc-can-unlock-onchain-finance
- ML-KEM 尺寸（Open Quantum Safe）：https://openquantumsafe.org/liboqs/algorithms/kem/ml-kem
- 脚本与读数：本文件夹
