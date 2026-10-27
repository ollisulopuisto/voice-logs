class VoiceLogsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._items = [];
    this._query = "";
    this._includeHidden = false;
    this._offset = 0;
    this._total = 0;
    this._ready = false;
    this._archiveKey = "";
    this._activeKey = "";
    this._requestId = 0;
  }

  setConfig(config) {
    this._config = config || {};
    this._pageSize = Math.min(100, Math.max(5, Number(this._config.page_size) || 20));
    this._ensureDom();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._ready) return;
    const state = hass.states[this._config?.entity || "sensor.voice_logs_latest"];
    const attrs = state?.attributes || {};
    const archiveKey = `${attrs.history_updated || ""}:${attrs.total_conversations || 0}`;
    const activeKey = JSON.stringify(attrs.active || null);
    if (archiveKey !== this._archiveKey) {
      this._archiveKey = archiveKey;
      this._fetchPage(0);
    }
    if (activeKey !== this._activeKey) {
      this._activeKey = activeKey;
      this._renderLive(attrs.active || null);
    }
  }

  getCardSize() {
    return 8;
  }

  static getStubConfig() {
    return {};
  }

  _ensureDom() {
    if (this._ready) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; color:var(--primary-text-color); }
        ha-card { padding:16px; overflow:hidden; }
        h2 { font-size:1.2rem; margin:0 0 14px; }
        .toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
        input[type=search] { flex:1 1 200px; min-width:130px; box-sizing:border-box; padding:10px 12px;
          border:1px solid var(--divider-color); border-radius:12px; color:var(--primary-text-color);
          background:var(--card-background-color); font:inherit; }
        label { display:flex; gap:8px; align-items:center; font-size:.9rem; color:var(--secondary-text-color); }
        .live { margin-bottom:12px; }
        .live:empty { display:none; }
        .status { color:var(--secondary-text-color); font-size:.85rem; text-align:center; margin:4px 0 10px; }
        .turn { padding:8px 0; border-bottom:1px solid var(--divider-color); }
        .bubble-row { display:flex; margin:5px 0; }
        .bubble-row.user { justify-content:flex-end; }
        .bubble-row.assistant { justify-content:flex-start; }
        .bubble { max-width:88%; white-space:pre-wrap; overflow-wrap:anywhere; user-select:text;
          padding:10px 14px; line-height:1.4; border-radius:18px; }
        .user .bubble { color:var(--text-primary-color,#fff); background:var(--primary-color);
          border-bottom-right-radius:4px; }
        .assistant .bubble { background:var(--secondary-background-color); border-bottom-left-radius:4px; }
        .meta { display:flex; gap:10px; align-items:center; flex-wrap:wrap; color:var(--secondary-text-color);
          font-size:.78rem; margin:6px 2px 3px; }
        button { border:0; border-radius:9px; padding:6px 10px; color:var(--primary-color);
          background:color-mix(in srgb, var(--primary-color) 12%, transparent); cursor:pointer; font:inherit; }
        button[disabled] { opacity:.45; cursor:default; }
        details { margin-top:6px; font-size:.84rem; color:var(--secondary-text-color); }
        summary { cursor:pointer; width:max-content; }
        .debug { display:grid; grid-template-columns:max-content 1fr; gap:3px 10px; margin:8px 0; }
        .debug dt { opacity:.75; } .debug dd { margin:0; overflow-wrap:anywhere; color:var(--primary-text-color); }
        .empty, .error { padding:16px 4px; text-align:center; color:var(--secondary-text-color); }
        .error { color:var(--error-color); }
        .pager { display:flex; justify-content:center; padding-top:14px; }
        .count { color:var(--secondary-text-color); font-size:.8rem; margin-left:auto; }
        .hidden-tag { color:var(--warning-color); }
      </style>
      <ha-card>
        <h2></h2>
        <div class="live"></div>
        <div class="toolbar">
          <input class="search" type="search" placeholder="Hae kysymyksistä ja vastauksista…" aria-label="Hae keskusteluista">
          <label><input class="show-hidden" type="checkbox"> Näytä piilotetut</label>
          <span class="count"></span>
        </div>
        <div class="error" hidden></div>
        <div class="history"></div>
        <div class="pager"><button class="more" type="button">Näytä vanhemmat</button></div>
      </ha-card>`;

    this.shadowRoot.querySelector("h2").textContent = this._config?.title || "Puheavustajan keskustelut";
    const search = this.shadowRoot.querySelector(".search");
    search.addEventListener("input", () => {
      this._query = search.value;
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(() => this._fetchPage(0), 250);
    });
    this.shadowRoot.querySelector(".show-hidden").addEventListener("change", (event) => {
      this._includeHidden = event.target.checked;
      this._fetchPage(0);
    });
    this.shadowRoot.querySelector(".more").addEventListener("click", () => {
      this._offset += this._pageSize;
      this._fetchPage(this._offset, true);
    });
    this.shadowRoot.querySelector(".history").addEventListener("click", (event) => {
      const button = event.composedPath().find((item) => item?.dataset?.action && item?.dataset?.id);
      if (button) this._setHidden(button.dataset.id, button.dataset.action === "hide");
    });
    this._ready = true;
  }

  async _fetchPage(offset, append = false) {
    if (!this._hass || !this._ready) return;
    const requestId = ++this._requestId;
    const error = this.shadowRoot.querySelector(".error");
    error.hidden = true;
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "voice_logs/history/list",
        query: this._query,
        include_hidden: this._includeHidden,
        offset,
        limit: this._pageSize,
      });
      if (requestId !== this._requestId) return;
      this._total = result.total;
      this._offset = result.offset;
      this._items = append ? [...this._items, ...result.items] : result.items;
      this._render();
    } catch (err) {
      if (requestId !== this._requestId) return;
      error.textContent = `Keskusteluhistoriaa ei voitu ladata: ${err.message || err}`;
      error.hidden = false;
    }
  }

  async _setHidden(id, hidden) {
    try {
      await this._hass.callService("voice_logs", hidden ? "hide_conversation" : "restore_conversation", {
        conversation_id: id,
      });
      await this._fetchPage(0);
    } catch (err) {
      const error = this.shadowRoot.querySelector(".error");
      error.textContent = `Keskustelun päivitys epäonnistui: ${err.message || err}`;
      error.hidden = false;
    }
  }

  _render() {
    if (!this._ready) return;
    const root = this.shadowRoot.querySelector(".history");
    root.replaceChildren(...this._items.map((item) => this._renderTurn(item)));
    const count = this.shadowRoot.querySelector(".count");
    count.textContent = this._total ? `${this._total} keskustelua` : "";
    const hasMore = this._items.length < this._total;
    this.shadowRoot.querySelector(".more").hidden = !hasMore;
    this.shadowRoot.querySelector(".pager").hidden = !hasMore;
    if (!this._items.length && !this._query) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Keskustelut tulevat tähän, kun käytät Assistia.";
      root.append(empty);
    } else if (!this._items.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Ei hakutuloksia.";
      root.append(empty);
    }
  }

  _renderLive(turn) {
    if (!this._ready) return;
    const root = this.shadowRoot.querySelector(".live");
    root.replaceChildren();
    if (!turn) return;
    const box = document.createElement("div");
    box.className = "turn";
    const label = document.createElement("div");
    label.className = "status";
    label.textContent = turn.status === "error" ? "Assist-virhe" : turn.finished ? "Valmis" : "Assist käsittelee pyyntöä…";
    box.append(label);
    box.append(this._bubble("user", turn.query));
    if (turn.answer) box.append(this._bubble("assistant", turn.answer));
    else if (!turn.finished) box.append(this._bubble("assistant", "…"));
    root.append(box);
  }

  _renderTurn(turn) {
    const box = document.createElement("article");
    box.className = "turn";
    box.append(this._bubble("user", turn.query));
    box.append(this._bubble("assistant", turn.answer || (turn.status === "error" ? "Assist ei pystynyt vastaamaan." : "Vastaus ei sisältänyt tekstiä.")));

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.append(document.createTextNode(this._formatDate(turn.created_at)));
    const debug = turn.debug || {};
    if (debug.mode) meta.append(document.createTextNode(debug.mode === "local" ? "Paikallinen" : "AI"));
    if (turn.hidden) {
      const hidden = document.createElement("span");
      hidden.className = "hidden-tag";
      hidden.textContent = "Piilotettu";
      meta.append(hidden);
    }
    const action = document.createElement("button");
    action.type = "button";
    action.dataset.id = turn.id;
    action.dataset.action = turn.hidden ? "restore" : "hide";
    action.textContent = turn.hidden ? "Palauta" : "Piilota";
    meta.append(action);
    box.append(meta);

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Debug-tiedot";
    details.append(summary);
    const list = document.createElement("dl");
    list.className = "debug";
    const labels = {
      pipeline_id: "Putki", satellite_id: "Satelliitti", language: "Kieli",
      stt_engine: "Puheentunnistus", intent_engine: "Keskusteluagentti",
      mode: "Käsittely", response_type: "Vastaustyyppi", tool_names: "Työkalut",
      error_code: "Virhekoodi", error_message: "Virhe",
    };
    for (const [key, labelText] of Object.entries(labels)) {
      const value = debug[key];
      if (value == null || value === "" || (Array.isArray(value) && !value.length)) continue;
      const dt = document.createElement("dt");
      dt.textContent = labelText;
      const dd = document.createElement("dd");
      dd.textContent = Array.isArray(value) ? value.join(", ") : String(value);
      list.append(dt, dd);
    }
    details.append(list);
    box.append(details);
    return box;
  }

  _bubble(role, text) {
    const row = document.createElement("div");
    row.className = `bubble-row ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text || "";
    row.append(bubble);
    return row;
  }

  _formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("fi-FI", {
      day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }
}

if (!customElements.get("voice-logs-card")) {
  customElements.define("voice-logs-card", VoiceLogsCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "voice-logs-card")) {
  window.customCards.push({
    type: "voice-logs-card",
    name: "Voice Logs",
    description: "Live Assist conversations and searchable persistent history",
    preview: true,
  });
}
