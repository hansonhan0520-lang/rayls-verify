// verify-brl1p.js
// Checks whether BRL1.p on Rayls is backed 1:1 by BRL1 locked on Polygon,
// and who could change that. Read-only: it only sends eth_call / eth_getLogs.
//
// Run it either way:
//   1. Node 18+:        node verify-brl1p.js
//   2. Browser console: open any https page, press F12, paste the whole file, press Enter.
// No wallet, no API key, no install.

const RPC_POLYGON = "https://polygon-bor-rpc.publicnode.com"; // public Polygon RPC (log queries kept to 5,000 blocks)
const RPC_RAYLS   = "https://mainnet-rpc.rayls.com";     // official Rayls RPC, used for current state
const API_RAYLS   = "https://explorer.rayls.com/api/v2";  // Rayls explorer API, used for event history
// On 17 Oct 2026 the public Rayls RPC returned no logs or receipts for the blocks where
// BRL1.p was deployed and its roles granted (around block 12437224), while the explorer
// had them. So Rayls-side history is read from the explorer and current state from the RPC.

const BRL1      = "0x5C067C80C00eCd2345b05E83A3e758eF799C40B5"; // BRL1 on Polygon
const LOCKBOX   = "0x3Ea6BaC7d4138BcC126D0F17aE10122B3620abA6"; // bridge vault on Polygon (LayerZero OFTAdapter)
const BRL1P     = "0xA069d3798FEAb32994aC5D98A9F011DA6024f334"; // BRL1.p on Rayls (ERC1967 proxy)
const ADAPTER   = "0xE56dDf65E311CddB71f69c0aC4D27E58B239D69a"; // RaylsMintBurnOFTAdapter on Rayls
const EP_POLYGON = "0x1a44076050125825900e736c501f859c50fe728c"; // LayerZero EndpointV2 on Polygon
const EID_POLYGON = 30109, EID_RAYLS = 30415;    // LayerZero endpoint IDs
const LOCKBOX_FROM_BLOCK = 95472945;  // Polygon block that created the lockbox

// keccak256 values, precomputed so the script needs no library
const ROLE = {
  DEFAULT_ADMIN: "0".repeat(64),
  MINTER:   "9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6",
  BURNER:   "3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a848",
  PAUSER:   "65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a",
  UPGRADER: "189ab7a9244df0848122154315af71fe140f3db0fe014031783b0946b8c9d2e3",
};
const TOPIC_TRANSFER     = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";
const TOPIC_ROLE_GRANTED = "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d";
const TOPIC_ROLE_REVOKED = "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b";
const TOPIC_UPGRADED     = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b";
const SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";

let id = 0;
// Public RPCs sit behind load balancers, so one node can briefly lag another.
// Retry a few times when a call errors or returns null.
async function rpc(url, method, params, tries = 4) {
  for (let i = 1; ; i++) {
    const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params }) });
    const j = await r.json();
    if (!j.error && j.result !== null && j.result !== undefined) return j.result;
    if (i >= tries) throw new Error(`${method} on ${url}: ${j.error ? j.error.message : "null result"}`);
    await new Promise((res) => setTimeout(res, 1500));
  }
}
const word = (a) => a.toLowerCase().replace("0x", "").padStart(64, "0");
const u32  = (n) => n.toString(16).padStart(64, "0");
const addrOf = (w) => "0x" + w.slice(-40);
const fmt = (wei) => { const neg = wei < 0n; const s = (neg ? -wei : wei).toString().padStart(19, "0"); return (neg ? "-" : "") + s.slice(0, -18).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + s.slice(-18, -12); };
const call = (url, to, data, block = "latest") => rpc(url, "eth_call", [{ to, data }, block]);

async function sumTransfers(url, token, fromBlock, toBlock, step, topics) {
  let total = 0n, count = 0;
  for (let b = fromBlock; b <= toBlock; b += step) {
    const logs = await rpc(url, "eth_getLogs", [{ address: token, fromBlock: "0x" + b.toString(16),
      toBlock: "0x" + Math.min(b + step - 1, toBlock).toString(16), topics }]);
    for (const l of logs) { total += BigInt(l.data); count++; }
  }
  return { total, count };
}
async function explorerLogs(address) {           // every log the explorer holds for a contract
  let out = [], next = null;
  do {
    const q = next ? "?" + new URLSearchParams(next) : "";
    const j = await (await fetch(`${API_RAYLS}/addresses/${address}/logs${q}`)).json();
    out = out.concat(j.items); next = j.next_page_params;
  } while (next);
  return out;
}
function decodeUln(hex) {
  const w = hex.slice(2).match(/.{64}/g);              // [0]=offset [1]=len [2]=tuple offset
  const t = w.slice(3);
  const confirmations = parseInt(t[0], 16), required = parseInt(t[1], 16), optional = parseInt(t[2], 16);
  const reqStart = parseInt(t[4], 16) / 32;
  const dvns = []; for (let i = 0; i < parseInt(t[reqStart], 16); i++) dvns.push(addrOf(t[reqStart + 1 + i]));
  return { confirmations, required, optional, dvns };
}

(async () => {
  const lines = []; const log = (s = "") => { lines.push(s); console.log(s); };
  const started = new Date().toISOString();
  // Read a few blocks behind the tip so every node behind the public RPC already has them.
  const pBlock = parseInt(await rpc(RPC_POLYGON, "eth_blockNumber", []), 16) - 5;
  const rBlock = parseInt(await rpc(RPC_RAYLS, "eth_blockNumber", []), 16) - 5;
  const pTime = new Date(parseInt((await rpc(RPC_POLYGON, "eth_getBlockByNumber", ["0x" + pBlock.toString(16), false])).timestamp, 16) * 1000).toISOString();
  const rTime = new Date(parseInt((await rpc(RPC_RAYLS, "eth_getBlockByNumber", ["0x" + rBlock.toString(16), false])).timestamp, 16) * 1000).toISOString();
  log(`BRL1.p backing check, run at ${started}`);
  log(`Polygon block ${pBlock} (${pTime})   Rayls block ${rBlock} (${rTime})`);

  log("\n[1] Stock: is every BRL1.p matched by BRL1 in the lockbox?");
  const locked = BigInt(await call(RPC_POLYGON, BRL1, "0x70a08231" + word(LOCKBOX), "0x" + pBlock.toString(16)));
  const supply = BigInt(await call(RPC_RAYLS, BRL1P, "0x18160ddd", "0x" + rBlock.toString(16)));
  log(`  BRL1 held by lockbox   ${fmt(locked)}   (raw ${locked})`);
  log(`  BRL1.p total supply    ${fmt(supply)}   (raw ${supply})`);
  log(`  lockbox - supply       ${fmt(locked - supply)}   ${locked >= supply ? "OK: lockbox >= supply" : "WARNING: supply exceeds lockbox"}`);

  log("\n[2] Flows: do locks match mints and unlocks match burns?");
  const Z = "0x" + "0".repeat(64), LB = "0x" + word(LOCKBOX);
  const lockedIn  = await sumTransfers(RPC_POLYGON, BRL1, LOCKBOX_FROM_BLOCK, pBlock, 5000, [TOPIC_TRANSFER, null, LB]);
  const lockedOut = await sumTransfers(RPC_POLYGON, BRL1, LOCKBOX_FROM_BLOCK, pBlock, 5000, [TOPIC_TRANSFER, LB, null]);
  const raylsLogs = await explorerLogs(BRL1P);
  const transfers = raylsLogs.filter((l) => l.topics[0] === TOPIC_TRANSFER && l.block_number <= rBlock);
  const sumIf = (f) => transfers.filter(f).reduce((a, l) => ({ total: a.total + BigInt(l.data), count: a.count + 1 }), { total: 0n, count: 0 });
  const minted = sumIf((l) => l.topics[1] === Z);
  const burned = sumIf((l) => l.topics[2] === Z);
  log(`  Polygon into lockbox   ${lockedIn.count} transfers, ${fmt(lockedIn.total)}`);
  log(`  Rayls minted           ${minted.count} mints,     ${fmt(minted.total)}`);
  log(`  Polygon out of lockbox ${lockedOut.count} transfers, ${fmt(lockedOut.total)}`);
  log(`  Rayls burned           ${burned.count} burns,     ${fmt(burned.total)}`);

  log("\n[3] Wiring: do the two sides point only at each other?");
  log(`  lockbox.token()            ${addrOf(await call(RPC_POLYGON, LOCKBOX, "0xfc0c546a"))}`);
  log(`  lockbox.peers(${EID_RAYLS})     ${addrOf(await call(RPC_POLYGON, LOCKBOX, "0xbb0b6a53" + u32(EID_RAYLS)))}`);
  log(`  adapter.token()            ${addrOf(await call(RPC_RAYLS, ADAPTER, "0xfc0c546a"))}`);
  log(`  adapter.peers(${EID_POLYGON})     ${addrOf(await call(RPC_RAYLS, ADAPTER, "0xbb0b6a53" + u32(EID_POLYGON)))}`);
  const grants = raylsLogs.filter((l) => l.topics[0] === TOPIC_ROLE_GRANTED);
  const revokes = raylsLogs.filter((l) => l.topics[0] === TOPIC_ROLE_REVOKED);
  const name = Object.fromEntries(Object.entries(ROLE).map(([k, v]) => ["0x" + v, k]));
  log(`  BRL1.p RoleGranted events: ${grants.length}, RoleRevoked events: ${revokes.length}`);
  for (const g of grants) log(`    ${name[g.topics[1]] || g.topics[1]} -> ${addrOf(g.topics[2])}  (tx ${g.transaction_hash})`);

  log("\n[4] Control: who can change the rules, and is it one key?");
  const impl = addrOf(await rpc(RPC_RAYLS, "eth_getStorageAt", [BRL1P, SLOT_IMPL, "latest"]));
  const upgrades = raylsLogs.filter((l) => l.topics[0] === TOPIC_UPGRADED);
  log(`  BRL1.p implementation ${impl}, Upgraded events: ${upgrades.length}`);
  const holders = [...new Set(grants.map((g) => addrOf(g.topics[2])))];
  for (const h of holders) {
    const roles = [];
    for (const [k, v] of Object.entries(ROLE))
      if (BigInt(await call(RPC_RAYLS, BRL1P, "0x91d14854" + v + word(h))) === 1n) roles.push(k);
    const code = await rpc(RPC_RAYLS, "eth_getCode", [h, "latest"]);
    log(`  ${h}  roles now: ${roles.join(", ") || "none"}  ${code === "0x" ? "(plain wallet, no contract code)" : "(contract)"}`);
  }
  for (const [label, url, c] of [["lockbox", RPC_POLYGON, LOCKBOX], ["adapter", RPC_RAYLS, ADAPTER]]) {
    const o = addrOf(await call(url, c, "0x8da5cb5b"));
    const code = await rpc(url, "eth_getCode", [o, "latest"]);
    log(`  ${label}.owner() ${o} ${code === "0x" ? "(plain wallet, no contract code)" : "(contract)"}`);
  }

  log("\n[5] Messages: who must sign off before the other side acts?");
  let dvnMeta = {};
  try { dvnMeta = await (await fetch("https://metadata.layerzero-api.com/v1/metadata/dvns")).json(); } catch (e) {}
  const dvnName = (chain, a) => { const d = (dvnMeta[chain] || {}).dvns || {};
    const k = Object.keys(d).find((x) => x.toLowerCase() === a); return k ? d[k].canonicalName : "unlisted"; };
  for (const [label, url, ep, oapp, remote, chain] of [
    ["Polygon -> Rayls (checked on Rayls)", RPC_RAYLS, null, ADAPTER, EID_POLYGON, "rayls"],
    ["Rayls -> Polygon (checked on Polygon)", RPC_POLYGON, EP_POLYGON, LOCKBOX, EID_RAYLS, "polygon"]]) {
    const endpoint = ep || addrOf(await call(url, oapp, "0x5e280f11"));
    const lib = addrOf((await call(url, endpoint, "0x402f8468" + word(oapp) + u32(remote))).slice(0, 66));
    const cfg = decodeUln(await call(url, endpoint, "0x2b3197b9" + word(oapp) + word(lib) + u32(remote) + u32(2)));
    log(`  ${label}: ${cfg.required} required DVNs, ${cfg.optional} optional, ${cfg.confirmations} source-chain confirmations`);
    for (const d of cfg.dvns) log(`    DVN ${d}  ${dvnName(chain, d)}`);
  }
  log("  DVN names from LayerZero's public registry: metadata.layerzero-api.com/v1/metadata/dvns");

  log("\n[6] Issuer layer: can BRL1 itself freeze the lockbox?");
  const reg = addrOf(await call(RPC_POLYGON, BRL1, "0xe6f29b05"));
  const has = await call(RPC_POLYGON, reg, "0xeefb7e9a" + word(LOCKBOX) + word(LOCKBOX) + u32(0x60) + u32(0));
  log(`  BRL1.paused() ${BigInt(await call(RPC_POLYGON, BRL1, "0x5c975abb")) === 1n}`);
  log(`  BRL1 access registry ${reg}, lockbox hasAccess = ${BigInt(has) === 1n}`);
  log(`  BRL1 total supply on Polygon ${fmt(BigInt(await call(RPC_POLYGON, BRL1, "0x18160ddd")))}`);

  log(`\nfinished ${new Date().toISOString()}`);
  if (typeof window !== "undefined") window.__brl1pReport = lines.join("\n");
})();
