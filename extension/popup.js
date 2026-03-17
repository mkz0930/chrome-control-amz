const $ = id => document.getElementById(id);
const logBox = $("logBox");

function addLog(msg) {
  const d = document.createElement("div");
  const t = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  d.textContent = `[${t}] ${msg}`;
  logBox.prepend(d);
  if (logBox.children.length > 15) logBox.lastChild.remove();
}

let port = null;

function connectPort() {
  try {
    port = chrome.runtime.connect({ name: "popup" });
    addLog("port 已连接");

    port.onMessage.addListener((msg) => {
      addLog(`收到: ${msg.type} connected=${msg.connected}`);
      if (msg.type === "status_update") {
        renderStatus(msg);
      }
    });

    port.onDisconnect.addListener(() => {
      addLog("port 断开");
      port = null;
    });

    port.postMessage({ type: "get_status" });
  } catch (e) {
    addLog("port 失败: " + e.message);
    readFromStorage();
  }
}

function readFromStorage() {
  chrome.storage.local.get(["relay_status"], (data) => {
    if (data.relay_status) {
      addLog("从 storage 读取");
      renderStatus(data.relay_status);
    } else {
      addLog("storage 无数据");
    }
  });
}

function renderStatus(data) {
  const card = $("statusCard");
  const isConn = data.connected;

  card.className = "status-card " + (isConn ? "connected" : "disconnected");
  $("statusText").innerHTML = isConn
    ? '<span class="indicator on"></span>已连接 ✅'
    : '<span class="indicator off"></span>未连接 ❌';

  let portVal = "—", serverVal = "—";
  const wsUrl = data.ws_url || "";
  if (wsUrl) {
    try {
      const u = new URL(wsUrl);
      portVal = u.port || "—";
      serverVal = u.hostname + ":" + (u.port || "—");
    } catch { serverVal = wsUrl; }
  }
  $("portText").textContent = portVal;
  $("serverText").textContent = serverVal;
  $("retryText").textContent = data.retry_count || 0;
}

$("refreshBtn").onclick = () => {
  addLog("手动刷新");
  if (port) {
    port.postMessage({ type: "get_status" });
  } else {
    readFromStorage();
    connectPort();
  }
};

$("reconnectBtn").onclick = () => {
  addLog("发起重连...");
  if (port) {
    port.postMessage({ type: "reconnect" });
  } else {
    connectPort();
    setTimeout(() => {
      if (port) port.postMessage({ type: "reconnect" });
    }, 500);
  }
};

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  $("urlDisplay").textContent = "当前标签页: " + (tabs[0]?.url || "无");
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.relay_status) {
    renderStatus(changes.relay_status.newValue);
  }
});

connectPort();
