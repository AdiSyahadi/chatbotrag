(function () {
  var API_URL = document.currentScript.getAttribute("data-server") || "";

  // ── Load Bootstrap Icons ────────────────────────────────────────
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

  // ── Toggle Button ───────────────────────────────────────────────
  var toggle = document.createElement("button");
  toggle.id = "rag-widget-toggle";
  toggle.type = "button";
  toggle.innerHTML = '<i class="bi bi-chat-dots-fill"></i>';
  toggle.title = "Chat";
  document.body.appendChild(toggle);

  // ── Chat Box ────────────────────────────────────────────────────
  var box = document.createElement("div");
  box.id = "rag-widget-box";
  document.body.appendChild(box);

  box.innerHTML =
    '<div id="rag-widget-header"><i class="bi bi-mortarboard-fill"></i> Tanya PMB</div>' +
    '<div id="rag-widget-messages"></div>' +
    '<div id="rag-widget-input-area">' +
    '<input id="rag-widget-input" type="text" placeholder="Ketik pertanyaan..." autocomplete="off">' +
    '<button id="rag-widget-send" type="button"><i class="bi bi-send-fill"></i></button>' +
    "</div>";

  var messages = document.getElementById("rag-widget-messages");
  var input = document.getElementById("rag-widget-input");
  var sendBtn = document.getElementById("rag-widget-send");

  // ── State (controlled by data-open attribute + CSS !important) ──
  var _chatOpen = false;

  function openChat() {
    _chatOpen = true;
    box.setAttribute("data-open", "true");
    input.focus();
    if (messages.children.length === 0) {
      addMsg("Halo! Ada yang bisa saya bantu?", "bot");
    }
  }

  function closeChat() {
    _chatOpen = false;
    box.removeAttribute("data-open");
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
    if (_chatOpen) { closeChat(); } else { openChat(); }
  });

  // Stop ALL events inside box from leaking out
  ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "touchstart", "touchend", "focusin", "focusout"].forEach(function (evt) {
    box.addEventListener(evt, function (e) { e.stopPropagation(); }, true);
  });

  // ── Input ───────────────────────────────────────────────────────
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); send(); }
  });

  sendBtn.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    send();
  });

  // ── Helpers ─────────────────────────────────────────────────────
  function addMsg(text, type) {
    var div = document.createElement("div");
    div.className = "rag-msg " + type;
    if (type === "bot") { div.innerHTML = renderMd(text); }
    else { div.textContent = text; }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function addLoading() {
    var div = document.createElement("div");
    div.className = "rag-msg bot";
    div.setAttribute("data-loading", "1");
    div.innerHTML = '<span class="rag-spinner"></span> Memproses...';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function removeLoading() {
    var el = box.querySelector('[data-loading="1"]');
    if (el) el.remove();
  }

  function renderMd(text) {
    var s = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
    s = s.replace(/`(.+?)`/g, "<code>$1</code>");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  var sending = false;

  function send() {
    if (sending) return;
    var q = input.value.trim();
    if (!q) return;
    sending = true;
    input.value = "";
    addMsg(q, "user");
    addLoading();
    sendBtn.disabled = true;

    var xhr = new XMLHttpRequest();
    xhr.open("POST", API_URL + "/api/v1/chat", true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      removeLoading();
      if (xhr.status === 200) {
        try {
          var data = JSON.parse(xhr.responseText);
          addMsg(data.reply || data.error || "Terjadi kesalahan.", "bot");
        } catch (e) {
          addMsg("Gagal memproses respons.", "bot");
        }
      } else {
        addMsg("Gagal terhubung ke server.", "bot");
      }
      sendBtn.disabled = false;
      sending = false;
    };
    xhr.onerror = function () {
      removeLoading();
      addMsg("Gagal terhubung ke server.", "bot");
      sendBtn.disabled = false;
      sending = false;
    };
    xhr.send(JSON.stringify({ message: q }));
  }
})();
