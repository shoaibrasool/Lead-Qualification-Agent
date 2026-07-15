(function () {
  var STORAGE_KEY = 'lq_session_id';
  var API_URL = '/chat';
  var script = document.currentScript;
  if (script && script.dataset.apiUrl) {
    API_URL = script.dataset.apiUrl;
  }

  var SLOT_RE = /^\d+\.\s+(.+)$/gm;

  var cssLink = document.querySelector('link[href*="widget.css"]');
  function loadCSS() {
    if (!cssLink) return '';
    try {
      var req = new XMLHttpRequest();
      req.open('GET', cssLink.href, false);
      req.send();
      return req.responseText;
    } catch (e) {
      return '';
    }
  }

  function genUUID() {
    try { return crypto.randomUUID(); } catch (e) {}
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function LeadQualWidget() {
    var stored = sessionStorage.getItem(STORAGE_KEY);
    this.sessionId = stored || genUUID();
    sessionStorage.setItem(STORAGE_KEY, this.sessionId);
    this.open = false;
    this.waiting = false;
    try {
      this._render();
      this._bind();
    } catch (e) {
      console.error('LeadQualWidget init failed:', e);
    }
  }

  LeadQualWidget.prototype._render = function () {
    var host = document.createElement('div');
    host.id = 'lq-host';
    var shadow = host.attachShadow({ mode: 'closed' });
    document.body.appendChild(host);

    var style = document.createElement('style');
    style.textContent = loadCSS() || (
      ':host{all:initial;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,Ubuntu,Cantarell,sans-serif}' +
      '*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}' +
      '.lq-bubble{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:#2563eb;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(37,99,235,0.35);display:flex;align-items:center;justify-content:center;z-index:999999;transition:transform .2s,box-shadow .2s;font-size:28px}' +
      '.lq-bubble:hover{transform:scale(1.08);box-shadow:0 6px 20px rgba(37,99,235,0.45)}' +
      '.lq-bubble.lq-open{display:none}' +
      '.lq-panel{position:fixed;bottom:24px;right:24px;width:380px;height:520px;background:#fff;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.18);display:none;flex-direction:column;z-index:999999;overflow:hidden;animation:lq-slideUp .25s ease-out}' +
      '.lq-panel.lq-open{display:flex}' +
      '@keyframes lq-slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}' +
      '.lq-header{background:linear-gradient(135deg,#1e40af,#2563eb);color:#fff;padding:14px 16px;flex-shrink:0;display:flex;justify-content:space-between;align-items:flex-start;gap:12px}' +
      '.lq-close{background:none;border:none;color:#fff;font-size:20px;cursor:pointer;padding:2px 4px;line-height:1;opacity:.8;transition:opacity .15s;flex-shrink:0}' +
      '.lq-close:hover{opacity:1}' +
      '.lq-header-title{font-size:16px;font-weight:600}' +
      '.lq-header-sub{font-size:12px;opacity:.85;margin-top:2px}' +
      '.lq-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#f8fafc}' +
      '.lq-message{max-width:80%;padding:10px 14px;border-radius:16px;font-size:14px;line-height:1.5;word-wrap:break-word;white-space:pre-wrap}' +
      '.lq-message.lq-user{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:4px}' +
      '.lq-message.lq-bot{align-self:flex-start;background:#fff;color:#1e293b;border:1px solid #e2e8f0;border-bottom-left-radius:4px}' +
      '.lq-message.lq-bot strong{font-weight:600}' +
      '.lq-message.lq-bot em{font-style:italic}' +
      '.lq-message.lq-bot code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-family:"SF Mono","Fira Code",monospace;font-size:13px}' +
      '.lq-message.lq-bot a{color:#2563eb;text-decoration:underline}' +
      '.lq-slot-buttons{align-self:flex-start;display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}' +
      '.lq-slot-btn{padding:8px 16px;border-radius:20px;border:1px solid #2563eb;background:#fff;color:#2563eb;font-size:13px;font-weight:500;cursor:pointer;transition:background .15s,color .15s}' +
      '.lq-slot-btn:hover{background:#2563eb;color:#fff}' +
      '.lq-typing{align-self:flex-start;display:none;align-items:center;gap:4px;padding:12px 18px;background:#fff;border:1px solid #e2e8f0;border-radius:16px;border-bottom-left-radius:4px}' +
      '.lq-typing.lq-visible{display:flex}' +
      '.lq-typing-dot{width:8px;height:8px;border-radius:50%;background:#94a3b8;animation:lq-bounce 1.4s infinite}' +
      '.lq-typing-dot:nth-child(2){animation-delay:.2s}' +
      '.lq-typing-dot:nth-child(3){animation-delay:.4s}' +
      '@keyframes lq-bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}' +
      '.lq-input-area{display:flex;align-items:center;gap:8px;padding:12px 16px;border-top:1px solid #e2e8f0;background:#fff;flex-shrink:0}' +
      '.lq-input{flex:1;border:1px solid #e2e8f0;border-radius:24px;padding:10px 16px;font-size:14px;outline:none;font-family:inherit;transition:border-color .15s}' +
      '.lq-input:focus{border-color:#2563eb}' +
      '.lq-send{width:40px;height:40px;border-radius:50%;border:none;background:#2563eb;color:#fff;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s,transform .15s;flex-shrink:0}' +
      '.lq-send:hover{background:#1d4ed8;transform:scale(1.05)}' +
      '.lq-send:disabled{background:#94a3b8;cursor:not-allowed;transform:none}' +
      '@media(max-width:480px){.lq-panel{bottom:0;right:0;width:100%;height:100%;border-radius:0}.lq-bubble{bottom:16px;right:16px}}'
    );
    shadow.appendChild(style);

    this._shadow = shadow;
    this.el = this._createElements(shadow);
    this._addWelcomeMessage();
  };

  LeadQualWidget.prototype._createElements = function (shadow) {
    var bubble = document.createElement('button');
    bubble.className = 'lq-bubble';
    bubble.setAttribute('aria-label', 'Open chat');
    bubble.textContent = '\uD83D\uDCAC';
    shadow.appendChild(bubble);

    var panel = document.createElement('div');
    panel.className = 'lq-panel';
    shadow.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'lq-header';
    header.innerHTML =
      '<div>' +
      '<div class="lq-header-title">Lead Qualifier</div>' +
      '<div class="lq-header-sub">We typically respond in seconds</div>' +
      '</div>' +
      '<button class="lq-close" aria-label="Close chat">\u2715</button>';
    panel.appendChild(header);

    var messages = document.createElement('div');
    messages.className = 'lq-messages';
    panel.appendChild(messages);

    var typing = document.createElement('div');
    typing.className = 'lq-typing';
    typing.innerHTML =
      '<div class="lq-typing-dot"></div>' +
      '<div class="lq-typing-dot"></div>' +
      '<div class="lq-typing-dot"></div>';
    messages.appendChild(typing);

    var inputArea = document.createElement('div');
    inputArea.className = 'lq-input-area';
    panel.appendChild(inputArea);

    var input = document.createElement('input');
    input.className = 'lq-input';
    input.type = 'text';
    input.placeholder = 'Type your message...';
    input.setAttribute('aria-label', 'Chat message');
    inputArea.appendChild(input);

    var send = document.createElement('button');
    send.className = 'lq-send';
    send.setAttribute('aria-label', 'Send');
    send.innerHTML = '\u25B6';
    inputArea.appendChild(send);

    var closeBtn = header.querySelector('.lq-close');

    return { bubble: bubble, panel: panel, messages: messages, typing: typing, input: input, send: send, close: closeBtn };
  };

  LeadQualWidget.prototype._bind = function () {
    var self = this;
    this.el.bubble.addEventListener('click', function () {
      self._toggle(true);
    });

    this.el.close.addEventListener('click', function () {
      self._toggle(false);
    });

    this.el.send.addEventListener('click', function () {
      self._send();
    });

    this.el.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        self._send();
      }
    });
  };

  LeadQualWidget.prototype._toggle = function (open) {
    this.open = open;
    this.el.bubble.classList.toggle('lq-open', open);
    this.el.panel.classList.toggle('lq-open', open);
    if (open) {
      this.el.input.focus();
      this._scrollBottom();
    }
  };

  LeadQualWidget.prototype._send = function () {
    if (this.waiting) return;
    var input = this.el.input;
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    this._addMessage(text, 'user');
    this._postMessage(text);
  };

  LeadQualWidget.prototype._postMessage = function (text) {
    var self = this;
    this.waiting = true;
    this.el.send.disabled = true;
    this.el.typing.classList.add('lq-visible');
    this._scrollBottom();

    var xhr = new XMLHttpRequest();
    xhr.open('POST', API_URL, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
      self.waiting = false;
      self.el.send.disabled = false;
      self.el.typing.classList.remove('lq-visible');
      if (xhr.status === 200) {
        var data = JSON.parse(xhr.responseText);
        self._handleReply(data);
      } else {
        self._addMessage('Sorry, something went wrong. Please try again.', 'bot');
        self._scrollBottom();
      }
    };
    xhr.onerror = function () {
      self.waiting = false;
      self.el.send.disabled = false;
      self.el.typing.classList.remove('lq-visible');
      self._addMessage('Network error. Please check your connection.', 'bot');
      self._scrollBottom();
    };
    xhr.send(JSON.stringify({ session_id: this.sessionId, message: text }));
  };

  LeadQualWidget.prototype._handleReply = function (data) {
    var reply = data.reply || '';
    this._addMessage(reply, 'bot');

    var times = this._extractTimes(reply);
    if (times.length > 0) {
      this._renderSlotButtons(times);
    }

    if (data.done) {
      this.el.input.disabled = true;
      this.el.send.disabled = true;
      this.el.input.placeholder = 'Conversation ended';
    }

    this._scrollBottom();
  };

  LeadQualWidget.prototype._renderSlotButtons = function (times) {
    var self = this;
    var container = document.createElement('div');
    container.className = 'lq-slot-buttons';

    var seen = {};
    times.forEach(function (t) {
      if (seen[t]) return;
      seen[t] = true;
      var btn = document.createElement('button');
      btn.className = 'lq-slot-btn';
      btn.textContent = t;
      btn.addEventListener('click', function () {
        self._addMessage(t, 'user');
        self._postMessage(t);
        container.remove();
      });
      container.appendChild(btn);
    });

    this.el.messages.appendChild(container);
  };

  LeadQualWidget.prototype._extractTimes = function (text) {
    var results = [];
    var match;
    SLOT_RE.lastIndex = 0;
    while ((match = SLOT_RE.exec(text)) !== null) {
      results.push(match[1]);
    }
    return results;
  };

  LeadQualWidget.prototype._addMessage = function (text, role) {
    var div = document.createElement('div');
    div.className = 'lq-message lq-' + role;

    if (role === 'bot') {
      div.innerHTML = this._renderMarkdown(this._escapeHtml(text));
    } else {
      div.textContent = text;
    }

    this.el.messages.appendChild(div);
  };

  LeadQualWidget.prototype._renderMarkdown = function (html) {
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>'
    );
    html = html.replace(/\n/g, '<br>');
    return html;
  };

  LeadQualWidget.prototype._escapeHtml = function (text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  };

  LeadQualWidget.prototype._scrollBottom = function () {
    var msgs = this.el.messages;
    requestAnimationFrame(function () {
      msgs.scrollTop = msgs.scrollHeight;
    });
  };

  LeadQualWidget.prototype._addWelcomeMessage = function () {
    if (this._welcomed) return;
    this._addMessage('Hello! I\u2019m here to help qualify your interest. What brings you here today?', 'bot');
    this._welcomed = true;
  };

  function init() {
    try {
      new LeadQualWidget();
    } catch (e) {
      console.error('LeadQualWidget init failed:', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
