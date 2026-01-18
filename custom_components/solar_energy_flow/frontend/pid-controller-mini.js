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

    .graph-container hui-history-graph-card {
      display: block;
      width: 100%;
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
      ],
    };
  }

  getCardSize() {
    return 6; // Increased to accommodate graph
  }

  updated(changedProperties) {
    if (changedProperties.has("hass") || changedProperties.has("config")) {
      this._updateData();
    }
    // Update graph after a short delay to ensure DOM is ready
    if (changedProperties.has("hass") || changedProperties.has("config")) {
      setTimeout(() => this._updateGraph(), 100);
    }
  }

  firstUpdated() {
    // Create graph after first render
    setTimeout(() => this._updateGraph(), 200);
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
      console.warn("PID Mini: Some entities not found", { pv: pvExists, sp: spExists, output: outputExists });
      return;
    }

    const container = this.shadowRoot?.getElementById("graph-container");
    if (!container) {
      return;
    }

    // Don't recreate if already exists
    const existingCard = container.querySelector("hui-history-graph-card");
    if (existingCard) {
      if (existingCard.hass !== this.hass) {
        existingCard.hass = this.hass;
      }
      return;
    }

    // Clear existing graph
    container.innerHTML = "";

    // Try to load card helpers
    try {
      const helpers = await window.loadCardHelpers();
      
      const cardConfig = {
        type: "history-graph",
        entities: [
          entityIds.pv,
          entityIds.sp,
          entityIds.output
        ],
        hours_to_show: 1,
        refresh_interval: 30,
      };

      const card = helpers.createCardElement(cardConfig);
      card.hass = this.hass;
      container.appendChild(card);
      
      // Force update after a short delay to ensure rendering
      setTimeout(() => {
        if (card.updateComplete) {
          card.updateComplete.then(() => {
            card.requestUpdate();
          });
        }
      }, 100);
    } catch (err) {
      console.error("PID Mini: Failed to create history graph:", err);
      container.innerHTML = `<div style='padding: 8px; color: var(--error-color, red); font-size: 12px;'>Graph error: ${err.message || err}</div>`;
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
    
    // Pass hass object - ensure it's the live reference
    popupCard.hass = this.hass;
    
    // Create a function to keep hass updated
    const updateHass = () => {
      if (this.hass) {
        // Always update to latest hass reference
        popupCard.hass = this.hass;
      }
    };
    
    // Update hass periodically to ensure it stays in sync
    const hassUpdateInterval = setInterval(() => {
      updateHass();
    }, 1000);
    
    dialog.addEventListener("closed", () => {
      // Clean up interval
      clearInterval(hassUpdateInterval);
      // Check if dialog is still in the DOM before removing
      if (dialog.parentNode === document.body) {
        try {
          document.body.removeChild(dialog);
        } catch (e) {
          // Dialog may have already been removed, ignore error
          console.debug("Dialog already removed:", e);
        }
      }
    });
    
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
          <div class="metric">
            <div class="metric-label">Status</div>
            <div class="metric-value">
              <span class="status-badge ${statusClass}">${d.status || "—"}</span>
            </div>
          </div>

          <div class="metric">
            <div class="metric-label">Mode</div>
            <div class="metric-value">${this._formatMode(d.runtime_mode)}</div>
          </div>

          <div class="metric">
            <div class="metric-label">PV</div>
            <div class="metric-value">${this._formatValue(d.pv_value)}</div>
          </div>

          <div class="metric">
            <div class="metric-label">SP</div>
            <div class="metric-value">${this._formatValue(d.effective_sp)}</div>
          </div>

          <div class="metric">
            <div class="metric-label">Error</div>
            <div
              class="metric-value ${d.error && d.error < 0 ? "negative" : ""}"
            >
              ${this._formatValue(d.error)}
            </div>
          </div>

          <div class="metric">
            <div class="metric-label">Output</div>
            <div class="metric-value">${this._formatValue(d.output)}</div>
          </div>
        </div>

        <div class="graph-container" id="graph-container"></div>

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

