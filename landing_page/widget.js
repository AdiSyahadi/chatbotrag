(function () {
  "use strict";

  var scriptTag = document.getElementById("rag-widget-script");
  var API_URL = scriptTag ? scriptTag.getAttribute("data-server") : "";

  // Determine chat endpoint: same-origin proxy or external API
  var CHAT_ENDPOINT = API_URL ? (API_URL + "/api/v1/chat") : "/api/chat";

  // ── Load Bootstrap Icons (skip if already loaded) ───────────────
  if (!document.querySelector('link[href*="bootstrap-icons"]')) {
    var biLink = document.createElement("link");
    biLink.rel = "stylesheet";
    biLink.href = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css";
    document.head.appendChild(biLink);
  }

  // ── Styles ──────────────────────────────────────────────────────
  var css = document.createElement("style");
  css.textContent = [
    "#rag-widget-toggle{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:#687EFF;color:#fff;border:none;cursor:pointer;box-shadow:0 2px 12px rgba(104,126,255,.25);display:flex;align-items:center;justify-content:center;z-index:99999;font-size:24px;transition:transform .15s}",
    "#rag-widget-toggle:hover{transform:scale(1.08)}",
    "#rag-widget-box{position:fixed;bottom:92px;right:24px;width:380px;max-height:520px;background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(104,126,255,.18);display:none;flex-direction:column;z-index:99999;overflow:hidden;font-family:'Segoe UI',system-ui,sans-serif}",
    "#rag-widget-box[data-open='true']{display:flex !important}",
    "#rag-widget-header{background:#687EFF;color:#fff;padding:14px 18px;font-weight:600;font-size:15px;display:flex;align-items:center;gap:8px}",
    "#rag-widget-messages{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;min-height:280px;max-height:360px}",
    ".rag-msg{max-width:85%;padding:10px 14px;border-radius:10px;font-size:14px;line-height:1.5;word-wrap:break-word}",
    ".rag-msg.user{align-self:flex-end;background:#687EFF;color:#fff;border-bottom-right-radius:2px}",
    ".rag-msg.bot{align-self:flex-start;background:#eef3ff;color:#1a202c;border-bottom-left-radius:2px}",
    ".rag-msg.bot strong{font-weight:700}",
    "#rag-widget-input-area{display:flex;gap:8px;padding:12px;border-top:1px solid #d8e2f0}",
    "#rag-widget-input{flex:1;padding:10px 12px;border:1px solid #d8e2f0;border-radius:8px;font-size:14px;font-family:inherit;outline:none}",
    "#rag-widget-input:focus{border-color:#80B3FF;box-shadow:0 0 0 2px rgba(128,179,255,.2)}",
    "#rag-widget-send{background:#687EFF;color:#fff;border:none;border-radius:8px;padding:10px 16px;cursor:pointer;font-size:14px;font-weight:600}",
    "#rag-widget-send:disabled{opacity:.5;cursor:not-allowed}",
    ".rag-spinner{display:inline-block;width:16px;height:16px;border:2px solid #d8e2f0;border-top-color:#687EFF;border-radius:50%;animation:rag-spin .6s linear infinite}",
    "@keyframes rag-spin{to{transform:rotate(360deg)}}",
    "@media(max-width:480px){#rag-widget-box{width:calc(100vw - 24px);right:12px;bottom:84px}}"
  ].join("");
  document.head.appendChild(css);

  // ── Build DOM ───────────────────────────────────────────────────
  var toggle = document.createElement("button");
  toggle.id = "rag-widget-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Buka chat");
  toggle.innerHTML = '<i class="bi bi-chat-dots-fill"></i>';
  document.body.appendChild(toggle);

  var box = document.createElement("div");
  box.id = "rag-widget-box";
  // Display controlled entirely by data-open attribute + CSS !important
  document.body.appendChild(box);

  box.innerHTML =
    '<div id="rag-widget-header"><i class="bi bi-mortarboard-fill"></i> Tanya PMB</div>' +
    '<div id="rag-widget-messages"></div>' +
    '<div id="rag-widget-input-area">' +
    '<input id="rag-widget-input" type="text" placeholder="Ketik pertanyaan..." autocomplete="off">' +
    '<button id="rag-widget-send" type="button" aria-label="Kirim"><i class="bi bi-send-fill"></i></button>' +
    "</div>";

  var msgContainer = document.getElementById("rag-widget-messages");
  var chatInput = document.getElementById("rag-widget-input");
  var sendBtn = document.getElementById("rag-widget-send");

  // ── State ───────────────────────────────────────────────────────
  var _chatOpen = false;
  var _sessionId = crypto.randomUUID();

  function openChat() {
    console.log("[WIDGET] openChat()");
    _chatOpen = true;
    box.setAttribute("data-open", "true");
  }

  function closeChat() {
    console.log("[WIDGET] closeChat()");
    _chatOpen = false;
    box.removeAttribute("data-open");
  }

  // ── Toggle ──────────────────────────────────────────────────────
  toggle.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    console.log("[WIDGET] toggle click, open=" + _chatOpen);

    if (_chatOpen) {
      closeChat();
    } else {
      openChat();
      chatInput.focus();
      if (msgContainer.children.length === 0) {
        appendMsg("Halo! Aku Tanya PMB 👋 Mau tanya soal jurusan, pendaftaran, biaya kuliah, atau info kampus lainnya? Tanya aja!", "bot");
      }
    }
  });

  // ── Isolate box events ──────────────────────────────────────────
  ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "touchstart", "touchend", "focusin", "focusout"].forEach(function (evt) {
    box.addEventListener(evt, function (e) { e.stopPropagation(); }, true);
  });

  // ── Input handling ──────────────────────────────────────────────
  chatInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      doSend();
    }
  });

  sendBtn.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    doSend();
  });

  // ── Message helpers ─────────────────────────────────────────────
  function appendMsg(text, role) {
    var div = document.createElement("div");
    div.className = "rag-msg " + role;
    if (role === "bot") {
      div.innerHTML = safeMd(text);
    } else {
      div.textContent = text;
    }
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  function showLoading() {
    var div = document.createElement("div");
    div.className = "rag-msg bot";
    div.setAttribute("data-loading", "true");
    div.innerHTML = '<span class="rag-spinner"></span> Lagi nyiapin jawaban...';
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  function hideLoading() {
    var el = msgContainer.querySelector('[data-loading="true"]');
    if (el) msgContainer.removeChild(el);
  }

  function safeMd(text) {
    var s = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
    s = s.replace(/`(.+?)`/g, "<code>$1</code>");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  // ── Send logic ──────────────────────────────────────────────────
  var sending = false;

  function doSend() {
    if (sending) return;
    var q = chatInput.value.trim();
    if (!q) return;

    sending = true;
    chatInput.value = "";
    appendMsg(q, "user");
    showLoading();
    sendBtn.disabled = true;

    var xhr = new XMLHttpRequest();
    xhr.open("POST", CHAT_ENDPOINT, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      hideLoading();
      if (xhr.status === 200) {
        try {
          var data = JSON.parse(xhr.responseText);
          appendMsg(data.reply || data.error || "Terjadi kesalahan.", "bot");
        } catch (e) {
          appendMsg("Gagal memproses respons.", "bot");
        }
      } else {
        appendMsg("Gagal terhubung ke server.", "bot");
      }
      sendBtn.disabled = false;
      sending = false;
    };
    xhr.onerror = function () {
      hideLoading();
      appendMsg("Gagal terhubung ke server.", "bot");
      sendBtn.disabled = false;
      sending = false;
    };
    xhr.send(JSON.stringify({ message: q, session_id: _sessionId }));
  }
})();
