// OpenClaw Browser Relay - Background Service Worker
// Auto-connects to local WebSocket server on extension load

let ws = null;
let connected = false;
let retryCount = 0;
const MAX_RETRIES = 10;
const WS_URL = "ws://172.25.0.1:19000";

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  
  console.log(`[relay] connecting to ${WS_URL}... (attempt ${retryCount + 1})`);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    connected = true;
    retryCount = 0;
    ws.send(JSON.stringify({ type: "extension", version: "1.0.0" }));
    console.log("[relay] ✅ connected to OpenClaw server");
    updateIcon(true);
    broadcastStatus(true);
  };

  ws.onclose = () => {
    connected = false;
    updateIcon(false);
    broadcastStatus(false);
    
    if (retryCount < MAX_RETRIES) {
      retryCount++;
      const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
      console.log(`[relay] ❌ disconnected, retrying in ${delay/1000}s...`);
      setTimeout(connect, delay);
    } else {
      console.log("[relay] ⚠️ max retries reached, stop reconnecting");
    }
  };

  ws.onerror = (e) => {
    console.error("[relay] ⚠️ ws error", e);
  };

  ws.onmessage = async (event) => {
    let cmd;
    try { 
      cmd = JSON.parse(event.data); 
    } catch { 
      console.log("[relay] ⚠️ Invalid JSON received");
      return; 
    }
    
    // Ignore messages without action (like extension identify)
    if (!cmd.action) {
      console.log("[relay] ← identify/heartbeat received");
      return;
    }
    
    console.log(`[relay] ← command: ${cmd.action}`);
    
    try {
      const result = await handleCommand(cmd);
      result.request_id = cmd.request_id;
      result.timestamp = Date.now();
      
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(result));
      }
    } catch (e) {
      console.error("[relay] ⚠️ Command execution error:", e);
      ws.send(JSON.stringify({
        ok: false,
        error: e.message,
        stack: e.stack,
        request_id: cmd.request_id,
        timestamp: Date.now()
      }));
    }
  };
}

function updateIcon(on) {
  chrome.action.setBadgeText({ text: on ? "ON" : "" });
  chrome.action.setBadgeBackgroundColor({ color: on ? "#22c55e" : "#ef4444" });
}

function broadcastStatus(online) {
  chrome.runtime.sendMessage({ type: "status_change", connected: online }).catch(() => {});
}

async function getTargetTab(cmd) {
  if (cmd.tabId) {
    const tab = await chrome.tabs.get(cmd.tabId);
    return tab;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function handleCommand(cmd) {
  const startTime = Date.now();
  
  try {
    let result;
    
    switch (cmd.action) {
      case "status":
        result = { ok: true, connected, url: await getCurrentUrl() };
        break;
        
      case "screenshot":
        result = await cmdScreenshot(cmd);
        break;
        
      case "navigate":
        result = await cmdNavigate(cmd);
        break;
        
      case "get_url":
        result = await cmdGetUrl(cmd);
        break;
        
      case "get_text":
        result = await cmdGetText(cmd);
        break;
        
      case "get_html":
        result = await cmdGetHtml(cmd);
        break;
        
      case "click":
        result = await cmdClick(cmd);
        break;
        
      case "click_xy":
        result = await cmdClickXY(cmd);
        break;
        
      case "type":
        result = await cmdType(cmd);
        break;
        
      case "eval":
        result = await cmdEval(cmd);
        break;
        
      case "scroll":
        result = await cmdScroll(cmd);
        break;
        
      case "wait":
        result = await cmdWait(cmd);
        break;
        
      case "click_text":
        result = await cmdClickText(cmd);
        break;
        
      case "list_tabs":
        result = await cmdListTabs(cmd);
        break;
        
      case "switch_tab":
        result = await cmdSwitchTab(cmd);
        break;
        
      case "close_tab":
        result = await cmdCloseTab(cmd);
        break;
        
      case "new_tab":
        result = await cmdNewTab(cmd);
        break;
        
      case "get_cookies":
        result = await cmdGetCookies(cmd);
        break;
        
      case "set_cookies":
        result = await cmdSetCookies(cmd);
        break;
        
      case "download":
        result = await cmdDownload(cmd);
        break;
        
      default:
        result = { ok: false, error: `unknown action: ${cmd.action}` };
    }
    
    result.execution_time_ms = Date.now() - startTime;
    return result;
    
  } catch (e) {
    return { 
      ok: false, 
      error: e.message, 
      stack: e.stack,
      execution_time_ms: Date.now() - startTime 
    };
  }
}

// Command implementations
async function cmdScreenshot(cmd) {
  const dataUrl = await chrome.tabs.captureVisibleTab(null, { 
    format: cmd.format || "png",
    quality: cmd.quality || 100
  });
  return { ok: true, data: dataUrl };
}

async function cmdNavigate(cmd) {
  const tab = await getTargetTab(cmd);
  await chrome.tabs.update(tab.id, { url: cmd.url });
  
  if (cmd.waitForLoad !== false) {
    await waitForTabLoad(tab.id, cmd.timeout || 30000);
  }
  
  return { ok: true, url: cmd.url, tab_id: tab.id };
}

async function cmdGetUrl(cmd) {
  const tab = await getTargetTab(cmd);
  return { ok: true, url: tab.url, title: tab.title, tab_id: tab.id };
}

async function cmdGetText(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id, frameIds: cmd.frameIds ? [cmd.frameIds] : undefined },
    func: (selector) => {
      if (selector) {
        return document.querySelector(selector)?.innerText || "";
      }
      return document.body.innerText;
    },
    args: [cmd.selector || null],
  });
  return { ok: true, text: res.result };
}

async function cmdGetHtml(cmd) {
  const tab = await getTargetTab(cmd);
  const selector = cmd.selector || "body";
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (sel) => document.querySelector(sel)?.outerHTML || "",
    args: [selector],
  });
  return { ok: true, html: res.result };
}

async function cmdClick(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (sel, waitForNav) => {
      const el = document.querySelector(sel);
      if (!el) return { ok: false, error: "element not found" };
      
      const isLink = el.tagName === "A" && el.href;
      const isButton = el.tagName === "BUTTON" || el.role === "button";
      
      el.click();
      
      if (waitForNav && (isLink || isButton)) {
        return { ok: true, navigating: true };
      }
      return { ok: true, tag: el.tagName, text: el.innerText?.slice(0, 50) };
    },
    args: [cmd.selector, cmd.waitForNavigation || false],
  });
  return res.result;
}

async function cmdClickXY(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (x, y) => {
      const el = document.elementFromPoint(x, y);
      if (!el) return { ok: false, error: "no element at point" };
      
      el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, clientX: x, clientY: y }));
      el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, clientX: x, clientY: y }));
      el.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: x, clientY: y }));
      
      return { ok: true, tag: el.tagName, text: el.innerText?.slice(0, 50) };
    },
    args: [cmd.x, cmd.y],
  });
  return res.result;
}

async function cmdType(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (sel, text, clear, delay) => {
      const el = document.querySelector(sel);
      if (!el) return { ok: false, error: "element not found" };
      
      el.focus();
      if (clear) el.value = "";
      
      if (delay && delay > 0) {
        // Type slowly
        for (const char of text) {
          el.value += char;
          el.dispatchEvent(new Event("input", { bubbles: true }));
        }
      } else {
        el.value += text;
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }
      
      el.dispatchEvent(new Event("change", { bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      
      return { ok: true };
    },
    args: [cmd.selector, cmd.text, cmd.clear !== false, cmd.delay || 0],
  });
  return res.result;
}

async function cmdEval(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (code) => {
      try { 
        const result = eval(code);
        return { ok: true, result: result, type: typeof result }; 
      } catch (e) { 
        return { ok: false, error: e.message }; 
      }
    },
    args: [cmd.code],
  });
  return res.result;
}

async function cmdScroll(cmd) {
  const tab = await getTargetTab(cmd);
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (x, y, behavior) => window.scrollBy({ left: x || 0, top: y || 500, behavior: behavior || "smooth" }),
    args: [cmd.x || 0, cmd.y || 500, cmd.behavior || "smooth"],
  });
  return { ok: true };
}

async function cmdWait(cmd) {
  const ms = cmd.ms || 1000;
  await new Promise(r => setTimeout(r, ms));
  return { ok: true, waited_ms: ms };
}

async function cmdClickText(cmd) {
  const tab = await getTargetTab(cmd);
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (text, exact) => {
      const all = document.querySelectorAll('button,a,span,div,li,[role="button"]');
      
      // First pass: exact match on leaf nodes
      for (const el of all) {
        const t = el.innerText && el.innerText.trim();
        if (!t) continue;
        if ((exact && t === text) || (!exact && t.includes(text))) {
          if (el.children.length === 0 || el.tagName === 'BUTTON' || el.tagName === 'A') {
            el.click();
            return { ok: true, tag: el.tagName, text: t.slice(0, 80) };
          }
        }
      }
      
      // Second pass: any match
      for (const el of all) {
        const t = el.innerText && el.innerText.trim();
        if (t && ((exact && t === text) || (!exact && t.includes(text)))) {
          el.click();
          return { ok: true, tag: el.tagName, text: t.slice(0, 80) };
        }
      }
      
      return { ok: false, error: "text not found" };
    },
    args: [cmd.text, cmd.exact || false],
  });
  return res.result;
}

async function cmdListTabs(cmd) {
  const tabs = await chrome.tabs.query({ currentWindow: cmd?.currentWindowOnly !== false });
  return { 
    ok: true, 
    tabs: tabs.map(t => ({ 
      id: t.id, 
      url: t.url, 
      title: t.title, 
      active: t.active,
      favIconUrl: t.favIconUrl
    })) 
  };
}

async function cmdSwitchTab(cmd) {
  if (cmd.tabId) {
    await chrome.tabs.update(cmd.tabId, { active: true });
    return { ok: true, tab_id: cmd.tabId };
  } else if (cmd.index !== undefined) {
    const tabs = await chrome.tabs.query({ currentWindow: true });
    if (tabs[cmd.index]) {
      await chrome.tabs.update(tabs[cmd.index].id, { active: true });
      return { ok: true, tab_id: tabs[cmd.index].id };
    }
  }
  return { ok: false, error: "tab not found" };
}

async function cmdCloseTab(cmd) {
  const tabId = cmd.tabId || (await getTargetTab(cmd)).id;
  await chrome.tabs.remove(tabId);
  return { ok: true, closed_tab_id: tabId };
}

async function cmdNewTab(cmd) {
  const tab = await chrome.tabs.create({ url: cmd.url || "about:blank", active: cmd.active !== false });
  return { ok: true, tab_id: tab.id, url: tab.url };
}

async function cmdGetCookies(cmd) {
  const url = cmd.url || (await getActiveTab()).url;
  const cookies = await chrome.cookies.getAll({ url });
  return { ok: true, cookies, count: cookies.length };
}

async function cmdSetCookies(cmd) {
  const tab = await getTargetTab(cmd);
  const url = new URL(tab.url);
  
  for (const cookie of cmd.cookies) {
    await chrome.cookies.set({
      url: cmd.url || `${url.protocol}//${url.hostname}`,
      name: cookie.name,
      value: cookie.value,
      domain: cookie.domain,
      path: cookie.path || "/",
      secure: cookie.secure || false,
      httpOnly: cookie.httpOnly || false,
      expirationDate: cookie.expirationDate
    });
  }
  
  return { ok: true, set_count: cmd.cookies.length };
}

async function cmdDownload(cmd) {
  chrome.downloads.download({
    url: cmd.url,
    filename: cmd.filename,
    saveAs: cmd.saveAs || false
  });
  return { ok: true, downloading: cmd.url };
}

async function getCurrentUrl() {
  try {
    const tab = await getTargetTab(cmd);
    return tab.url;
  } catch {
    return null;
  }
}

function waitForTabLoad(tabId, timeout = 30000) {
  return new Promise((resolve) => {
    const listener = (id, info) => {
      if (id === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, timeout);
  });
}

// Initialize on extension load
console.log("[relay] 🚀 OpenClaw Browser Relay starting...");
connect();

// Keep service worker alive
setInterval(() => {
  chrome.runtime.getPlatformInfo(() => {});
}, 20000);

// 10-minute heartbeat to server
const HEARTBEAT_INTERVAL = 10 * 60 * 1000; // 10 minutes

function sendHeartbeat() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "heartbeat",
      timestamp: Date.now(),
      message: "10-minute heartbeat"
    }));
    console.log("[relay] ⏱️ 10-minute heartbeat sent");
  }
}

// Start heartbeat timer
let heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);

// Reset heartbeat on reconnection
const originalConnect = connect;
connect = function(...args) {
  const result = originalConnect.apply(this, args);
  
  // Clear previous timer and start new one
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
  
  return result;
};

// Status query from popup or content scripts
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "get_status") {
    sendResponse({ connected, ws_url: WS_URL, retry_count: retryCount });
  } else if (msg.type === "reconnect") {
    retryCount = 0;
    if (ws) ws.close();
    connect();
    sendResponse({ reconnecting: true });
  }
  return true;
});
