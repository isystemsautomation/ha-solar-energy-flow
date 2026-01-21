import { LitElement, html, css } from "lit";

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
    this._canvas = null;
    this._chart = null;
    this._graphInFlight = false;
    this._graphUpdateTimeout = null;
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
        this._scheduleGraphUpdate(800);
      }
    }
  }

  async firstUpdated() {
    if (this.config.show_chart) {
      await this._loadChartJS();
      setTimeout(() => this._updateGraph(), 200);
      this._graphInterval = setInterval(() => this._updateGraph(), 30000);
    }
  }

  _loadChartJS() {
    return new Promise((resolve, reject) => {
      if (window.Chart) {
        resolve();
        return;
      }

      const script = document.createElement("script");
      // Load Chart.js from the local integration static path so it works offline
      script.src = "/solar_energy_controller/frontend/chart.umd.min.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Chart.js"));
      document.head.appendChild(script);
    });
  }

  disconnectedCallback() {
    if (this._graphInterval) {
      clearInterval(this._graphInterval);
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
    }
    if (this._graphUpdateTimeout) {
      clearTimeout(this._graphUpdateTimeout);
    }
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }

  _scheduleGraphUpdate(delayMs = 800) {
    if (this._graphUpdateTimeout) {
      clearTimeout(this._graphUpdateTimeout);
    }
    this._graphUpdateTimeout = setTimeout(() => {
      this._updateGraph();
    }, delayMs);
  }

  async _ensureChart() {
    if (this._chart) {
      return;
    }

    const container = this.shadowRoot?.getElementById("graph-container");
    if (!container) {
      return;
    }

    // Create canvas once
    if (!this._canvas) {
      this._canvas = document.createElement("canvas");
      this._canvas.style.width = "100%";
      this._canvas.style.height = "200px";
      this._canvas.style.display = "block";
      container.appendChild(this._canvas);
    }

    // Create Chart.js instance once
    const ctx = this._canvas.getContext("2d");
    this._chart = new window.Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "PV",
            data: [],
            borderColor: "#2196F3",
            backgroundColor: "transparent",
            tension: 0.1,
          },
          {
            label: "SP",
            data: [],
            borderColor: "#FF9800",
            backgroundColor: "transparent",
            tension: 0.1,
          },
          {
            label: "OUTPUT",
            data: [],
            borderColor: "#9C27B0",
            backgroundColor: "transparent",
            tension: 0.1,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: {
              usePointStyle: true,
              padding: 10,
              font: {
                size: 11,
              },
            },
          },
          tooltip: {
            enabled: true,
          },
        },
        scales: {
          x: {
            grid: {
              color: "var(--divider-color, #ddd)",
            },
            ticks: {
              color: "var(--secondary-text-color, #888)",
              font: {
                size: 10,
              },
              maxTicksLimit: 5,
              callback: function(value, index, ticks) {
                const label = this.getLabelForValue(value);
                if (!label) return "";
                const date = new Date(label);
                return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
              },
            },
          },
          y: {
            grid: {
              color: "var(--divider-color, #ddd)",
            },
            ticks: {
              color: "var(--secondary-text-color, #888)",
              font: {
                size: 10,
              },
              callback: function(value) {
                return value.toFixed(0);
              },
            },
          },
        },
      },
    });

    // Setup resize observer
    if (!this._resizeObserver) {
      this._resizeObserver = new ResizeObserver(() => {
        if (this._chart) {
          this._chart.resize();
          this._chart.update("none");
        }
      });
      this._resizeObserver.observe(container);
    }
  }

  async _fetchHistory() {
    const entityIds = this._getEntityIds();
    if (!entityIds || !this.hass) {
      return null;
    }

    const pvExists = this.hass.states[entityIds.pv];
    const spExists = this.hass.states[entityIds.sp];
    const outputExists = this.hass.states[entityIds.output];
    
    if (!pvExists || !spExists || !outputExists) {
      return null;
    }

    try {
      const startTime = new Date(Date.now() - 3600000);
      const entityList = `${entityIds.pv},${entityIds.sp},${entityIds.output}`;
      const url = `history/period/${startTime.toISOString()}?filter_entity_id=${encodeURIComponent(entityList)}&minimal_response=false&significant_changes_only=false`;
      
      const history = await this.hass.callApi("GET", url);

      if (!history || !Array.isArray(history)) {
        return null;
      }

      return this._parseHistory(history, entityIds);
    } catch (err) {
      console.error("Error fetching history:", err);
      return null;
    }
  }

  _parseHistory(history, entityIds) {
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
    
    if (allTimes.size === 0) {
      return null;
    }

    const sortedTimes = Array.from(allTimes).sort((a, b) => a - b);
    
    // Interpolate data points to common time axis
    const labels = sortedTimes.map(t => new Date(t).toISOString());
    const pvData = this._interpolateToTimeAxis(data.pv, sortedTimes);
    const spData = this._interpolateToTimeAxis(data.sp, sortedTimes);
    const outputData = this._interpolateToTimeAxis(data.output, sortedTimes);

    return {
      labels,
      datasets: [
        { label: "PV", data: pvData },
        { label: "SP", data: spData },
        { label: "OUTPUT", data: outputData },
      ],
    };
  }

  _interpolateToTimeAxis(points, timeAxis) {
    if (points.length === 0) {
      return new Array(timeAxis.length).fill(null);
    }

    const result = [];
    let pointIndex = 0;

    for (const time of timeAxis) {
      // Find the closest point or interpolate
      while (pointIndex < points.length - 1 && points[pointIndex + 1].time < time) {
        pointIndex++;
      }

      if (pointIndex >= points.length) {
        result.push(points[points.length - 1]?.value ?? null);
      } else if (points[pointIndex].time === time) {
        result.push(points[pointIndex].value);
      } else if (pointIndex === 0) {
        result.push(points[0].value);
      } else {
        // Interpolate between two points
        const prev = points[pointIndex - 1];
        const next = points[pointIndex];
        const ratio = (time - prev.time) / (next.time - prev.time);
        result.push(prev.value + (next.value - prev.value) * ratio);
      }
    }

    return result;
  }

  _updateTraces(points) {
    if (!this._chart || !points) {
      return;
    }

    this._chart.data.labels = points.labels;
    points.datasets.forEach((dataset, index) => {
      if (this._chart.data.datasets[index]) {
        this._chart.data.datasets[index].data = dataset.data;
      }
    });

    this._chart.update("none");
  }

  async _updateGraph() {
    if (this._graphInFlight) {
      return;
    }

    this._graphInFlight = true;

    try {
      await this._ensureChart();
      
      if (!this._chart) {
        this._graphInFlight = false;
        return;
      }

      const points = await this._fetchHistory();
      
      if (points) {
        this._updateTraces(points);
      }
    } catch (err) {
      console.error("Error updating graph:", err);
      const container = this.shadowRoot?.getElementById("graph-container");
      if (container && !this._chart) {
        const errorMsg = err?.message || (typeof err === 'string' ? err : JSON.stringify(err));
        container.innerHTML = `<div style='padding: 8px; color: var(--error-color, red); font-size: 12px;'>Graph error: ${errorMsg}</div>`;
      }
    } finally {
      this._graphInFlight = false;
    }
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
    
    dialog.appendChild(popupCard);
    document.body.appendChild(dialog);
    dialog.show();
    
    setTimeout(() => {
      const shadowRoot = dialog.shadowRoot;
      if (!shadowRoot) return;
      
      const header = shadowRoot.querySelector(".mdc-dialog__header") || 
                     shadowRoot.querySelector("h2")?.parentElement;
      
      if (header && !header.querySelector("mwc-icon-button")) {
        header.style.position = "relative";
        header.style.display = "flex";
        header.style.alignItems = "center";
        header.style.paddingLeft = "56px";
        
        const closeButton = document.createElement("mwc-icon-button");
        closeButton.style.cssText = "position: absolute; left: 8px; top: 50%; transform: translateY(-50%); --mdc-icon-button-size: 40px; --mdc-icon-size: 24px; z-index: 10; color: var(--primary-text-color);";
        const closeIcon = document.createElement("ha-icon");
        closeIcon.setAttribute("icon", "mdi:close");
        closeButton.appendChild(closeIcon);
        closeButton.addEventListener("click", () => dialog.close());
        
        header.insertBefore(closeButton, header.firstChild);
      }
    }, 500);
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

