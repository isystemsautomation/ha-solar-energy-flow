import { LitElement, html, css } from "https://cdn.jsdelivr.net/gh/lit/dist@2/core/lit-core.min.js";

class PIDControllerMini extends LitElement {
  static properties = {
    hass: { type: Object },
    config: { type: Object },
    _data: { state: true },
  };

  static styles = css`
    :host {
      display: block;
    }

    ha-card {
      padding: 16px;
      cursor: pointer;
    }

    ha-card:hover {
      box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 3px 1px -2px rgba(0, 0, 0, 0.2));
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .title {
      font-size: 16px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .compact-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }

    .metric {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .metric-label {
      font-size: 12px;
      color: var(--secondary-text-color);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .metric-value {
      font-size: 16px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .metric-value.negative {
      color: var(--error-color);
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--divider-color);
    }

    .status-badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
      background-color: var(--info-color, #039be5);
      color: var(--text-primary-color, #fff);
    }

    .status-badge.running {
      background-color: var(--success-color, #4caf50);
    }

    .status-badge.disabled {
      background-color: var(--disabled-color, #9e9e9e);
    }

    .graph-container {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--divider-color);
      min-height: 200px;
    }

    .graph-container ha-card {
      box-shadow: none;
      padding: 0;
    }

    .graph-container canvas {
      display: block;
      width: 100%;
      max-width: 100%;
    }
  `;

  constructor() {
    super();
    this._data = {};
  }

  setConfig(config) {
    if (!config.pid_entity) {
      throw new Error("pid_entity is required");
    }
    this.config = {
      title: "PID Controller",
      show_status: true,
      show_mode: true,
      show_pv: true,
      show_sp: true,
      show_error: true,
      show_output: true,
      show_chart: true,
      ...config,
    };
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: "pid_entity",
          required: true,
          selector: {
            entity: {
              domain: "sensor",
            },
          },
        },
        {
          name: "title",
          default: "PID Controller",
          selector: {
            text: {},
          },
        },
        {
          name: "show_status",
          label: "Show Status",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_mode",
          label: "Show Mode",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_pv",
          label: "Show PV",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_sp",
          label: "Show SP",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_error",
          label: "Show Error",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_output",
          label: "Show Output",
          default: true,
          selector: {
            boolean: {},
          },
        },
        {
          name: "show_chart",
          label: "Show Chart",
          default: true,
          selector: {
            boolean: {},
          },
        },
      ],
    };
  }

  getCardSize() {
    return 6;
  }

  updated(changedProperties) {
    if (changedProperties.has("hass") || changedProperties.has("config")) {
      this._updateData();
      if (this.config.show_chart) {
        setTimeout(() => this._updateGraph(), 100);
      }
    }
  }

  firstUpdated() {
    if (this.config.show_chart) {
      setTimeout(() => this._updateGraph(), 200);
      this._graphInterval = setInterval(() => this._updateGraph(), 30000);
    }
  }

  disconnectedCallback() {
    if (this._graphInterval) {
      clearInterval(this._graphInterval);
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
    }
  }

  async _updateGraph() {
    const entityIds = this._getEntityIds();
    if (!entityIds || !this.hass) {
      return;
    }

    // Verify entities exist
    const pvExists = this.hass.states[entityIds.pv];
    const spExists = this.hass.states[entityIds.sp];
    const outputExists = this.hass.states[entityIds.output];
    
    if (!pvExists || !spExists || !outputExists) {
      return;
    }

    const container = this.shadowRoot?.getElementById("graph-container");
    if (!container) {
      return;
    }

    container.innerHTML = "";

    // Create canvas for line chart
    const canvas = document.createElement("canvas");
    const containerWidth = container.offsetWidth || 400;
    canvas.width = containerWidth;
    canvas.height = 200;
    canvas.style.width = "100%";
    canvas.style.height = "200px";
    canvas.style.display = "block";
    container.appendChild(canvas);

    // Fetch history data
    try {
      const startTime = new Date(Date.now() - 3600000);
      const entityList = `${entityIds.pv},${entityIds.sp},${entityIds.output}`;
      const url = `history/period/${startTime.toISOString()}?filter_entity_id=${encodeURIComponent(entityList)}&minimal_response=false&significant_changes_only=false`;
      
      console.log("PID Mini: Fetching history for entities:", entityIds);
      const history = await this.hass.callApi("GET", url);
      console.log("PID Mini: History response:", history?.length, "entity histories");

      if (!history || !Array.isArray(history)) {
        throw new Error("Invalid history data format");
      }

      this._drawChart(canvas, history, entityIds);
      
      const resizeObserver = new ResizeObserver(() => {
        if (canvas.parentElement) {
          const newWidth = canvas.parentElement.offsetWidth;
          if (newWidth !== canvas.width) {
            canvas.width = newWidth;
            this._drawChart(canvas, history, entityIds);
          }
        }
      });
      resizeObserver.observe(container);
      this._resizeObserver = resizeObserver;
    } catch (err) {
      const errorMsg = err?.message || (typeof err === 'string' ? err : JSON.stringify(err));
      container.innerHTML = `<div style='padding: 8px; color: var(--error-color, red); font-size: 12px;'>Graph error: ${errorMsg}</div>`;
    }
  }

  _drawChart(canvas, history, entityIds) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const padding = 40;

    ctx.clearRect(0, 0, width, height);

    if (!history || history.length === 0) {
      ctx.fillStyle = "var(--secondary-text-color, #888)";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No data available", width / 2, height / 2);
      return;
    }

    const data = { pv: [], sp: [], output: [] };
    const allTimes = new Set();
    
    if (Array.isArray(history)) {
      history.forEach((entityHistory) => {
        if (!Array.isArray(entityHistory) || entityHistory.length === 0) return;
        
        const firstState = entityHistory[0];
        if (!firstState?.entity_id) return;
        
        const entityId = firstState.entity_id;
        
        entityHistory.forEach((state) => {
          if (!state) return;
          
          const time = new Date(state.last_changed || state.last_updated);
          if (isNaN(time.getTime())) return;
          
          allTimes.add(time.getTime());
          
          const value = parseFloat(state.state);
          if (isNaN(value)) return;
          
          if (entityId === entityIds.pv) {
            data.pv.push({ time: time.getTime(), value });
          } else if (entityId === entityIds.sp) {
            data.sp.push({ time: time.getTime(), value });
          } else if (entityId === entityIds.output) {
            data.output.push({ time: time.getTime(), value });
          }
        });
      });
    }
    
    if (data.pv.length === 0 && data.sp.length > 0) {
      console.warn("PID Mini: No PV data found. Expected entity:", entityIds.pv);
    }

    if (allTimes.size === 0) {
      ctx.fillStyle = "var(--secondary-text-color, #888)";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No data available", width / 2, height / 2);
      return;
    }

    const sortedTimes = Array.from(allTimes).sort((a, b) => a - b);
    const timeRange = sortedTimes[sortedTimes.length - 1] - sortedTimes[0];
    if (timeRange === 0) return;

    const allValues = [...data.pv, ...data.sp, ...data.output].map(d => d.value);
    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    const valueRange = maxValue - minValue || 1;

    ctx.strokeStyle = "var(--divider-color, #ddd)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    ctx.strokeStyle = "var(--divider-color, #ddd)";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
      const y = padding + (height - 2 * padding) * (1 - i / 5);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    ctx.fillStyle = "var(--secondary-text-color, #888)";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    for (let i = 0; i <= 4; i++) {
      const timeIndex = Math.floor((sortedTimes.length - 1) * i / 4);
      const time = new Date(sortedTimes[timeIndex]);
      const x = padding + (width - 2 * padding) * (i / 4);
      const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      ctx.fillText(timeStr, x, height - padding + 20);
    }

    ctx.textAlign = "right";
    for (let i = 0; i <= 5; i++) {
      const value = minValue + valueRange * (1 - i / 5);
      const y = padding + (height - 2 * padding) * (i / 5);
      ctx.fillText(value.toFixed(0), padding - 5, y + 4);
    }

    const colors = { pv: "#2196F3", sp: "#FF9800", output: "#9C27B0" };

    Object.keys(colors).forEach((key) => {
      if (data[key].length === 0) {
        console.warn(`PID Mini: No data points for ${key.toUpperCase()}`);
        return;
      }

      ctx.strokeStyle = colors[key];
      ctx.lineWidth = 2;
      ctx.beginPath();

      data[key].forEach((point, index) => {
        const x = padding + (width - 2 * padding) * ((point.time - sortedTimes[0]) / timeRange);
        const y = padding + (height - 2 * padding) * (1 - (point.value - minValue) / valueRange);

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
    });

    const legendY = padding + 10;
    let legendX = width - padding - 100;
    Object.keys(colors).forEach((key) => {
      const hasData = data[key] && data[key].length > 0;
      ctx.fillStyle = colors[key];
      ctx.fillRect(legendX, legendY, 12, 2);
      ctx.fillStyle = hasData ? "var(--primary-text-color, #000)" : "var(--disabled-text-color, #999)";
      ctx.font = "11px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(key.toUpperCase() + (hasData ? "" : " (no data)"), legendX + 15, legendY + 8);
      legendX -= 80;
    });
  }

  _updateData() {
    if (!this.hass || !this.config) return;

    const state = this.hass.states[this.config.pid_entity];
    const data = {};

    if (state && state.attributes) {
      const attrs = state.attributes;
      data.enabled = attrs.enabled ?? false;
      data.runtime_mode = attrs.runtime_mode || "AUTO_SP";
      data.pv_value = attrs.pv_value ?? null;
      data.effective_sp = attrs.effective_sp ?? null;
      data.error = attrs.error ?? null;
      data.output = attrs.output ?? null;
      data.status = attrs.status || "unknown";
    }

    this._data = data;
  }

  _formatValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
      return value.toFixed(1);
    }
    return String(value);
  }

  _formatMode(mode) {
    if (!mode) return "—";
    return mode.replace(/_/g, " ");
  }

  _getEntityIds() {
    if (!this.config || !this.config.pid_entity) return null;
    
    const statusEntity = this.config.pid_entity;
    const deviceName = statusEntity.replace(/^sensor\./, "").replace(/_status$/, "");
    
    return {
      pv: `sensor.${deviceName}_pv_value`,
      sp: `sensor.${deviceName}_effective_sp`,
      output: `sensor.${deviceName}_output`,
    };
  }

  _openPopup(ev) {
    if (ev) {
      ev.stopPropagation();
    }

    if (
      this.hass.services["browser_mod"] &&
      this.hass.services["browser_mod"]["popup"]
    ) {
      this.hass.callService("browser_mod", "popup", {
        title: this.config.title || "PID Controller",
        card: {
          type: "custom:pid-controller-popup",
          pid_entity: this.config.pid_entity,
        },
        size: "large",
      });
      return;
    }

    const dialog = document.createElement("ha-dialog");
    dialog.heading = this.config.title || "PID Controller";
    dialog.hideActions = false;
    dialog.scrimClickAction = "close";
    dialog.escapeKeyAction = "close";
    
    const closeButton = document.createElement("mwc-icon-button");
    closeButton.setAttribute("slot", "heading");
    closeButton.style.cssText = "position: absolute; left: 8px; top: 50%; transform: translateY(-50%); --mdc-icon-button-size: 40px; --mdc-icon-size: 24px;";
    const closeIcon = document.createElement("ha-icon");
    closeIcon.setAttribute("icon", "mdi:close");
    closeButton.appendChild(closeIcon);
    closeButton.addEventListener("click", () => dialog.close());
    
    const popupCard = document.createElement("pid-controller-popup");
    popupCard.setConfig({ pid_entity: this.config.pid_entity });
    popupCard.hass = this.hass;
    
    const updateHass = () => {
      if (this.hass) {
        popupCard.hass = this.hass;
      }
    };
    
    const hassUpdateInterval = setInterval(updateHass, 1000);
    
    dialog.addEventListener("closed", () => {
      clearInterval(hassUpdateInterval);
      if (dialog.parentNode === document.body) {
        try {
          document.body.removeChild(dialog);
        } catch (e) {
          // Ignore
        }
      }
    });
    
    dialog.appendChild(closeButton);
    dialog.appendChild(popupCard);
    document.body.appendChild(dialog);
    dialog.show();
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    const d = this._data;
    const statusClass =
      d.status === "running" ? "running" : d.enabled === false ? "disabled" : "";

    return html`
      <ha-card @click=${this._openPopup}>
        <div class="header">
          <div class="title">${this.config.title}</div>
        </div>

        <div class="compact-grid">
          ${this.config.show_status ? html`
          <div class="metric">
            <div class="metric-label">Status</div>
            <div class="metric-value">
              <span class="status-badge ${statusClass}">${d.status || "—"}</span>
            </div>
          </div>
          ` : ""}

          ${this.config.show_mode ? html`
          <div class="metric">
            <div class="metric-label">Mode</div>
            <div class="metric-value">${this._formatMode(d.runtime_mode)}</div>
          </div>
          ` : ""}

          ${this.config.show_pv ? html`
          <div class="metric">
            <div class="metric-label">PV</div>
            <div class="metric-value">${this._formatValue(d.pv_value)}</div>
          </div>
          ` : ""}

          ${this.config.show_sp ? html`
          <div class="metric">
            <div class="metric-label">SP</div>
            <div class="metric-value">${this._formatValue(d.effective_sp)}</div>
          </div>
          ` : ""}

          ${this.config.show_error ? html`
          <div class="metric">
            <div class="metric-label">Error</div>
            <div
              class="metric-value ${d.error && d.error < 0 ? "negative" : ""}"
            >
              ${this._formatValue(d.error)}
            </div>
          </div>
          ` : ""}

          ${this.config.show_output ? html`
          <div class="metric">
            <div class="metric-label">Output</div>
            <div class="metric-value">${this._formatValue(d.output)}</div>
          </div>
          ` : ""}
        </div>

        ${this.config.show_chart ? html`
          <div class="graph-container" id="graph-container"></div>
        ` : ""}

        <div class="actions">
          <mwc-button outlined label="Open Editor" @click=${this._openPopup}></mwc-button>
        </div>
      </ha-card>
    `;
  }
}

customElements.define("pid-controller-mini", PIDControllerMini);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "pid-controller-mini",
  name: "PID Controller Mini",
  description: "Compact dashboard card for PID controller with popup editor",
  preview: false,
});

