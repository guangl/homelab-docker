import "./haws-9.9.0.umd.js";

const { Auth, ERR_INVALID_AUTH, callService, createConnection, getAuth } = globalThis.HAWS;
const haUrl = "https://ha.guangluo.top";
const authOptions = {
  hassUrl: haUrl,
  clientId: location.origin + "/",
  redirectUrl: location.origin + "/smart-home",
  limitHassInstance: true,
};
const loginAttemptKey = "glance-ha-login-attempt";
const sessionKey = "glance-ha-session";
const accessNote = "连接 HA 后可操作空调和灯具。";
const connectedNote = "已连接";
const climatePower = { turnOff: 128, turnOn: 256 };
const modeLabels = {
  off: "关闭", heat: "制热", cool: "制冷", auto: "自动",
  dry: "除湿", fan_only: "送风", heat_cool: "冷热自动",
};
const climateDevices = [
  { room: "卧室", name: "空调", entity: "climate.lumi_cn_974734680_mcn02" },
  { room: "书房", name: "空调", entity: "climate.lumi_cn_974447483_mcn02" },
];
const lightingDevices = [
  { room: "卧室", name: "氛围灯", entity: "light.xiaomi_cn_1206585635_03wh_s_3_ambient_light" },
  { room: "书房", name: "氛围灯", entity: "light.xiaomi_cn_1160217220_02wh_s_3_ambient_light" },
  { room: "书房", name: "吸顶灯", entity: "light.yeelink_cn_394481736_ceiling22_s_2_light" },
];
const devices = [...climateDevices, ...lightingDevices];

const states = new Map();
const pending = new Set();
let panel, auth, connection;
let views = [];
let status = accessNote;
let busy = false;
let subscribed = false;
let sessionGeneration = 0;

function updateState(event) {
  for (const [entity, item] of Object.entries(event.a ?? {})) {
    states.set(entity, { state: item.s, attributes: { ...item.a } });
  }
  for (const [entity, change] of Object.entries(event.c ?? {})) {
    const item = states.get(entity);
    if (!item) continue;
    const additions = change["+"] ?? {};
    const attributes = { ...item.attributes, ...additions.a };
    for (const attribute of change["-"]?.a ?? []) delete attributes[attribute];
    states.set(entity, { state: additions.s ?? item.state, attributes });
  }
  for (const entity of event.r ?? []) states.delete(entity);
  render();
}

function availableModes(item) {
  const modes = item?.attributes.hvac_modes;
  return Array.isArray(modes) ? Object.keys(modeLabels).filter(mode => modes.includes(mode)) : [];
}

function temperatureStep(item, direction) {
  if (!["auto", "cool", "heat"].includes(item?.state)) return;
  const { temperature, min_temp: min, max_temp: max, target_temp_step, supported_features } = item.attributes;
  if (!(supported_features & 1)) return;
  if (![temperature, min, max].every(Number.isFinite)) return;
  const step = Number.isFinite(target_temp_step) && target_temp_step > 0 ? target_temp_step : 1;
  const next = Math.round((temperature + step * direction) * 100) / 100;
  if (next >= min && next <= max) return next;
}

function setPowerSwitch(button, on, enabled) {
  button.setAttribute("aria-checked", on);
  button.disabled = !enabled;
}

function renderDevice(view) {
  const item = states.get(view.device.entity);
  const state = item?.state;
  const available = Boolean(state && state !== "unavailable" && state !== "unknown");
  const writable = connection?.connected && subscribed && available && !pending.has(view.device.entity);
  if (view.modes) {
    const on = available && state !== "off";
    const powerFeature = on ? climatePower.turnOff : climatePower.turnOn;
    setPowerSwitch(view.toggle, on, writable && (item.attributes.supported_features & powerFeature));
    const modes = availableModes(item);
    const modeKey = modes.join(",");
    if (view.modeKey !== modeKey) {
      view.modes.replaceChildren(...modes.map(mode => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.mode = mode;
        button.textContent = modeLabels[mode];
        button.setAttribute("aria-label", view.device.room + view.device.name + modeLabels[mode]);
        return button;
      }));
      view.modeKey = modeKey;
    }
    for (const button of view.modes.children) {
      button.setAttribute("aria-pressed", button.dataset.mode === state);
      button.disabled = !writable;
    }
    const target = item?.attributes.temperature;
    view.target.textContent = available && Number.isFinite(target) ? `${target} °C` : "—";
    view.lower.disabled = !writable || temperatureStep(item, -1) === undefined;
    view.raise.disabled = !writable || temperatureStep(item, 1) === undefined;
    view.state.textContent = available ? (modeLabels[state] ?? "状态未知") : "不可用";
  } else {
    const on = state === "on";
    const known = on || state === "off";
    setPowerSwitch(view.toggle, on, writable && known);
    view.row.toggleAttribute("data-unavailable", !known);
    view.state.textContent = known ? (on ? "已开启" : "已关闭") : (state === "unavailable" ? "离线" : "状态未知");
  }
  if (!subscribed) view.state.textContent = "等待连接";
}

function render() {
  if (!panel) return;
  const connect = panel.querySelector("[data-connect]");
  connect.hidden = Boolean(connection);
  connect.disabled = busy;
  panel.querySelector("[data-disconnect]").hidden = !connection;
  const statusLine = panel.querySelector("[data-control-status]");
  statusLine.textContent = status;
  statusLine.toggleAttribute("data-compact", status === connectedNote);
  statusLine.toggleAttribute("data-online", Boolean(connection?.connected && subscribed));
  panel.querySelector("[data-control-grid]").hidden = !connection;
  views.forEach(renderDevice);
}

async function send(device, service, data = {}) {
  if (!connection?.connected || !subscribed || pending.has(device.entity)) return;
  const current = connection;
  pending.add(device.entity);
  status = `正在发送${device.room}${device.name}指令…`;
  render();
  try {
    await callService(current, device.entity.split(".")[0], service, data, { entity_id: device.entity });
    if (current === connection) status = `${device.room}${device.name}指令已发送，以设备状态为准。`;
  } catch (error) {
    if (current === connection) {
      status = error?.code === "unauthorized"
        ? "当前 HA 账号没有操作这台设备的权限。"
        : `${device.room}${device.name}未接受指令，请检查设备或连接。`;
    }
  } finally {
    if (current === connection) pending.delete(device.entity);
    render();
  }
}

function makePowerSwitch(device) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ha-power-switch";
  toggle.setAttribute("role", "switch");
  toggle.setAttribute("aria-label", device.room + device.name + "开关");
  setPowerSwitch(toggle, false, false);
  toggle.addEventListener("click", () => {
    const action = toggle.getAttribute("aria-checked") === "true" ? "turn_off" : "turn_on";
    void send(device, action);
  });
  return toggle;
}

function makeClimate(device) {
  const row = document.createElement("section");
  row.className = "ha-control-card ha-control-device";
  row.innerHTML = `
    <div class="ha-control-card-header"><div><h3></h3><span class="ha-control-state"></span></div></div>
    <div class="ha-climate-temperature">
      <button type="button">−</button>
      <div><span>设定温度</span><output class="ha-control-target"></output></div>
      <button type="button">+</button>
    </div>
    <div class="ha-climate-modes" role="group"></div>`;
  const label = device.room + device.name;
  row.querySelector("h3").textContent = label;
  const target = row.querySelector("output");
  target.setAttribute("aria-label", label + "设定温度");
  const modes = row.querySelector(".ha-climate-modes");
  modes.setAttribute("aria-label", label + "模式");
  modes.addEventListener("click", event => {
    const hvac_mode = event.target.closest("button[data-mode]")?.dataset.mode;
    const item = states.get(device.entity);
    if (hvac_mode !== item?.state && availableModes(item).includes(hvac_mode)) {
      void send(device, "set_hvac_mode", { hvac_mode });
    }
  });
  const [lower, raise] = row.querySelectorAll("button");
  for (const [button, direction, action] of [[lower, -1, "调低"], [raise, 1, "调高"]]) {
    button.setAttribute("aria-label", action + label + "设定温度");
    button.addEventListener("click", () => {
      const temperature = temperatureStep(states.get(device.entity), direction);
      if (temperature !== undefined) void send(device, "set_temperature", { temperature });
    });
  }
  const toggle = makePowerSwitch(device);
  row.querySelector(".ha-control-card-header").append(toggle);
  return { device, row, state: row.querySelector(".ha-control-state"), modes, target, lower, raise, toggle };
}

function makeLight(device) {
  const row = document.createElement("div");
  row.className = "ha-control-device ha-control-light";
  row.innerHTML = '<div><strong></strong><span class="ha-control-state"></span></div>';
  row.querySelector("strong").textContent = device.room + device.name;
  const toggle = makePowerSwitch(device);
  row.append(toggle);
  return { device, row, state: row.querySelector(".ha-control-state"), toggle };
}

function saveSession(tokens) {
  try {
    // Keep a signed-out marker so an older tab cannot migrate its previous session back.
    localStorage.setItem(sessionKey, JSON.stringify(tokens));
    sessionStorage.removeItem(sessionKey);
    return;
  } catch {
    // Fall back to a tab session when the browser blocks persistent storage.
  }
  try {
    if (tokens) sessionStorage.setItem(sessionKey, JSON.stringify(tokens));
    else sessionStorage.removeItem(sessionKey);
  } catch {
    // A blocked store still allows an in-memory connection.
  }
}

function sessionWriter(expectedToken) {
  const generation = ++sessionGeneration;
  return tokens => {
    if (generation !== sessionGeneration || !tokens) return;
    if (expectedToken && loadSession()?.refresh_token !== expectedToken) return;
    saveSession(tokens);
    expectedToken = tokens.refresh_token;
  };
}

function parseSession(raw) {
  try {
    const tokens = JSON.parse(raw);
    if (tokens?.hassUrl === haUrl && tokens.clientId === authOptions.clientId &&
        typeof tokens.access_token === "string" && tokens.access_token &&
        typeof tokens.refresh_token === "string" && tokens.refresh_token &&
        Number.isFinite(tokens.expires)) return tokens;
  } catch {
    // Discard malformed saved sessions.
  }
}

function loadSession() {
  try {
    const shared = localStorage.getItem(sessionKey);
    if (shared !== null) return parseSession(shared);
  } catch {
    // Try the per-tab store when persistent storage is blocked.
  }
  try {
    const previous = parseSession(sessionStorage.getItem(sessionKey));
    if (previous) saveSession(previous);
    return previous;
  } catch {
    // A browser with storage disabled can still use a live connection.
  }
}

function restoreSession() {
  const tokens = loadSession();
  if (!tokens) return false;
  const savedAuth = new Auth(tokens, sessionWriter(tokens.refresh_token));
  void connect(() => savedAuth, "正在恢复 Home Assistant 连接…");
  return true;
}

async function authorize() {
  if (restoreSession()) return;
  busy = true;
  status = "正在打开 Home Assistant 授权…";
  render();
  try {
    const response = await fetch(haUrl + "/.well-known/oauth-authorization-server", {
      credentials: "omit",
      signal: AbortSignal.timeout(8000),
    });
    const metadata = response.ok ? await response.json() : {};
    if (!metadata.code_challenge_methods_supported?.includes("S256") || !crypto.subtle) throw new Error("PKCE required");
    sessionStorage.setItem(loginAttemptKey, String(Date.now()));
    await getAuth(authOptions);
  } catch {
    busy = false;
    status = "无法开始 HA 授权，可从家庭面板操作设备。";
    render();
  }
}

function resetConnection(message) {
  sessionGeneration++;
  connection?.close();
  connection = undefined;
  const previousAuth = auth;
  auth = undefined;
  subscribed = false;
  pending.clear();
  states.clear();
  busy = false;
  status = message;
  render();
  return previousAuth;
}

async function disconnect(message = accessNote) {
  const saved = loadSession();
  const previousAuth = resetConnection(message);
  if (!saved || saved.refresh_token === previousAuth?.data.refresh_token) saveSession(null);
  try {
    if (previousAuth) await previousAuth.revoke();
  } catch {
    if (!connection && status === message) {
      status = "本页已断开，HA 会话撤销请求暂未完成。";
      render();
    }
  }
}

function authorizationFromCallback(query) {
  try {
    const attempt = Number(sessionStorage.getItem(loginAttemptKey));
    sessionStorage.removeItem(loginAttemptKey);
    const callback = JSON.parse(atob(query.get("state") ?? ""));
    if (attempt && Date.now() - attempt <= 10 * 60 * 1000 && callback.nonce && query.get("code")) {
      return getAuth({ ...authOptions, saveTokens: sessionWriter() });
    }
  } catch {
    // A callback without its original browser authorization attempt is unusable.
  } finally {
    history.replaceState(null, "", location.pathname);
  }
}

async function connect(resolveAuth, message) {
  const generation = sessionGeneration;
  busy = true;
  status = message;
  render();
  try {
    const resolved = await resolveAuth();
    if (generation !== sessionGeneration) return;
    auth = resolved;
    const connected = await createConnection({ auth, setupRetry: 0 });
    if (generation !== sessionGeneration) {
      connected.close();
      return;
    }
    connection = connected;
    connected.addEventListener("disconnected", () => {
      if (connected !== connection) return;
      states.clear();
      subscribed = false;
      status = "连接断开，正在重试…";
      render();
    });
    connected.addEventListener("reconnect-error", () => {
      if (connected === connection) void disconnect("HA 授权已失效，请重新连接。");
    });
    await connected.subscribeMessage(event => {
      if (connected !== connection) return;
      if (!subscribed) status = connectedNote;
      subscribed = true;
      updateState(event);
    }, { type: "subscribe_entities", entity_ids: devices.map(device => device.entity) });
    if (generation !== sessionGeneration) return;
    busy = false;
    render();
  } catch (error) {
    if (generation !== sessionGeneration) return;
    if (error === ERR_INVALID_AUTH) {
      await disconnect("HA 授权已失效，请重新连接。");
    } else {
      resetConnection("暂时无法连接 HA，请重试或打开家庭面板。");
    }
  }
}

function mount() {
  const nextPanel = document.querySelector(".ha-controls");
  if (nextPanel === panel) return;
  panel = nextPanel;
  if (!panel) return;
  panel.querySelector("[data-connect]").addEventListener("click", () => void authorize());
  panel.querySelector("[data-disconnect]").addEventListener("click", () => void disconnect());
  const climates = climateDevices.map(makeClimate);
  const lights = lightingDevices.map(makeLight);
  const lightingCard = document.createElement("section");
  lightingCard.className = "ha-control-card ha-lighting";
  lightingCard.innerHTML = "<h3>灯光</h3>";
  lightingCard.append(...lights.map(view => view.row));
  views = [...climates, ...lights];
  panel.querySelector("[data-control-grid]").replaceChildren(...climates.map(view => view.row), lightingCard);
  render();
}

mount();
new MutationObserver(mount).observe(document.getElementById("page"), { childList: true, subtree: true });
const callback = new URLSearchParams(location.search);
const authorization = callback.has("auth_callback") ? authorizationFromCallback(callback) : undefined;
if (authorization) {
  void connect(() => authorization, "正在连接 Home Assistant…");
} else if (!restoreSession() && callback.has("auth_callback")) {
  status = "HA 授权未完成，请重新连接。";
  render();
}

window.addEventListener("pagehide", () => resetConnection(accessNote));
window.addEventListener("pageshow", event => {
  if (event.persisted) restoreSession();
});
window.addEventListener("storage", event => {
  if (event.storageArea !== localStorage || (event.key !== sessionKey && event.key !== null)) return;
  const current = parseSession(localStorage.getItem(sessionKey));
  if (!current) {
    resetConnection("HA 已在其他标签页断开。");
  } else if (current.refresh_token !== parseSession(event.oldValue)?.refresh_token) {
    resetConnection(accessNote);
    restoreSession();
  }
});
