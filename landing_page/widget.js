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
    "#rag-widget-toggle{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:#25D366;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 15px rgba(37,211,102,.3);display:flex;align-items:center;justify-content:center;z-index:99999;font-size:24px;transition:transform .15s}",
    "#rag-widget-toggle:hover{transform:scale(1.08);background:#1ebe57}",
    "#rag-widget-box{position:fixed;bottom:92px;right:24px;width:380px;height:560px;max-height:calc(100vh - 120px);background:#efeae2;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.15);display:none;flex-direction:column;z-index:99999;overflow:hidden;font-family:'Inter',system-ui,sans-serif}",
    "#rag-widget-box[data-open='true']{display:flex !important}",
    "#rag-widget-header{background:#008069;color:#fff;padding:16px 20px;font-weight:600;font-size:16px;display:flex;align-items:center;gap:10px;box-shadow:0 1px 3px rgba(0,0,0,0.1);z-index:2}",
    "#rag-widget-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;background:#efeae2 url('https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png')}",
    ".rag-msg{max-width:85%;padding:8px 12px;border-radius:8px;font-size:14.5px;line-height:1.4;word-wrap:break-word;box-shadow:0 1px 1px rgba(0,0,0,0.1);position:relative}",
    ".rag-msg.user{align-self:flex-end;background:#d9fdd3;color:#111;border-top-right-radius:0}",
    ".rag-msg.bot{align-self:flex-start;background:#fff;color:#111;border-top-left-radius:0}",
    ".rag-msg.bot strong{font-weight:600}",
    ".rag-msg.system{align-self:center;background:#fff;color:#54656f;font-size:12px;padding:6px 12px;border-radius:10px;text-align:center;max-width:90%;margin:8px 0;box-shadow:0 1px 1px rgba(11,20,26,.05)}",
    "#rag-widget-input-area{display:flex;gap:10px;padding:12px 14px;background:#f0f2f5;border-top:1px solid #e9edef;align-items:center}",
    "#rag-widget-input{flex:1;padding:12px 14px;border:none;border-radius:8px;font-size:15px;font-family:inherit;outline:none;background:#fff}",
    "#rag-widget-input:focus{box-shadow:0 0 0 1px rgba(0,0,0,0.05)}",
    "#rag-widget-send{background:#00a884;color:#fff;border:none;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;box-shadow:0 1px 2px rgba(0,0,0,0.1)}",
    "#rag-widget-send:disabled{opacity:.5;cursor:not-allowed}",
    ".rag-spinner{display:inline-block;width:14px;height:14px;border:2px solid #e0ece6;border-top-color:#008069;border-radius:50%;animation:rag-spin .6s linear infinite}",
    "@keyframes rag-spin{to{transform:rotate(360deg)}}",
    "@media(max-width:480px){#rag-widget-box{width:calc(100vw - 24px);right:12px;bottom:84px}}"
  ].join("");
  document.head.appendChild(css);

  // ── Build DOM ───────────────────────────────────────────────────
  var toggle = document.createElement("button");
  toggle.id = "rag-widget-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Buka chat");
  toggle.innerHTML = '<i class="bi bi-robot"></i>';
  document.body.appendChild(toggle);

  var box = document.createElement("div");
  box.id = "rag-widget-box";
  // Display controlled entirely by data-open attribute + CSS !important
  document.body.appendChild(box);

  box.innerHTML =
    '<div id="rag-widget-header"><i class="bi bi-tree"></i> Selacau Bot</div>' +
    '<div id="rag-widget-messages"></div>' +
    '<div id="rag-widget-input-area">' +
    '<input id="rag-widget-input" type="text" placeholder="Tanya tentang surat atau informasi desa..." autocomplete="off">' +
    '<button id="rag-widget-send" type="button" aria-label="Kirim"><i class="bi bi-send-fill"></i></button>' +
    "</div>";

  var msgContainer = document.getElementById("rag-widget-messages");
  var chatInput = document.getElementById("rag-widget-input");
  var sendBtn = document.getElementById("rag-widget-send");

  var _chatOpen = false;
  var _sessionId = crypto.randomUUID();
  var _resetTimer = null;
  var _pollTimer = null;
  var _messageCount = 0;

  function resetSession() {
    _sessionId = crypto.randomUUID();
    appendMsg('<i class="bi bi-shield-lock-fill"></i> Sesi obrolan direset otomatis (3 menit tanpa aktivitas) demi keamanan.', 'system');
  }

  function activityPing() {
    if (_resetTimer) clearTimeout(_resetTimer);
    _resetTimer = setTimeout(resetSession, 3 * 60 * 1000); // 3 minutes
  }

  function openChat() {
    console.log("[WIDGET] openChat()");
    _chatOpen = true;
    box.setAttribute("data-open", "true");
    activityPing();
    startPolling();
  }

  function closeChat() {
    console.log("[WIDGET] closeChat()");
    _chatOpen = false;
    box.removeAttribute("data-open");
    stopPolling();
  }
  
  function startPolling() {
      if (_pollTimer) return;
      _pollTimer = setInterval(function() {
          var xhr = new XMLHttpRequest();
          xhr.open("GET", API_URL + "/api/v1/chat/" + _sessionId + "/poll?last_count=" + _messageCount, true);
          xhr.onreadystatechange = function () {
              if (xhr.readyState === 4 && xhr.status === 200) {
                  try {
                      var data = JSON.parse(xhr.responseText);
                      if (data.messages && data.messages.length > 0) {
                          data.messages.forEach(function(msg) {
                              var prefix = msg.real_sender === "ADMIN" ? "**[Admin]** " : "";
                              appendMsg(prefix + msg.text, msg.role);
                          });
                      }
                      _messageCount = data.total;
                  } catch(e) {}
              }
          };
          xhr.send();
      }, 3000);
  }
  
  function stopPolling() {
      if (_pollTimer) {
          clearInterval(_pollTimer);
          _pollTimer = null;
      }
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
        appendMsg('<i class="bi bi-lock-fill"></i> Pesan dilindungi dengan enkripsi end-to-end.', 'system');
        appendMsg("Halo! Saya Selacau Bot 👋 Ada yang bisa dibantu terkait informasi surat-menyurat atau pelayanan Desa Selacau?", "bot");
      }
    }
  });

  // ── Isolate box events ──────────────────────────────────────────
  ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "touchstart", "touchend", "focusin", "focusout"].forEach(function (evt) {
    box.addEventListener(evt, function (e) { e.stopPropagation(); }, false);
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
    } else if (role === "system") {
      div.innerHTML = text;
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
    stopPolling(); // Hentikan polling agar tidak menimpa pesan saat proses kirim

    var xhr = new XMLHttpRequest();
    xhr.open("POST", CHAT_ENDPOINT, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      hideLoading();
      if (xhr.status === 200) {
        try {
          var data = JSON.parse(xhr.responseText);
          if (data.reply !== "_SILENT_") {
              appendMsg(data.reply || data.error || "Terjadi kesalahan.", data.role || "bot");
          }
          if (data.total !== undefined) {
              _messageCount = data.total; // Sinkronkan hitungan dengan database server
          }
          activityPing(); // Reset timer on successful bot response
        } catch (e) {
          appendMsg("Gagal memproses respons.", "bot");
        }
      } else {
        appendMsg("Gagal terhubung ke server.", "bot");
      }
      sendBtn.disabled = false;
      sending = false;
      startPolling(); // Resume polling
    };
    xhr.onerror = function () {
      hideLoading();
      appendMsg("Gagal terhubung ke server.", "bot");
      sendBtn.disabled = false;
      sending = false;
      startPolling(); // Resume polling
    };
    xhr.send(JSON.stringify({ message: q, session_id: _sessionId }));
  }
})();
