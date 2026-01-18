import { LitElement, html, css } from "https://cdn.jsdelivr.net/gh/lit/dist@2/core/lit-core.min.js";

class PIDControllerPopup extends LitElement {
  static properties = {
    hass: { type: Object },
    config: { type: Object },
    _data: { state: true },
    _edited: { state: true },
  };

  static styles = css`
    :host {
      display: block;
    }

    ha-card {
      padding: 16px;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--divider-color);
    }

    .title {
      font-size: 20px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .section {
      margin-bottom: 24px;
    }

    .section-title {
      font-size: 14px;
      font-weight: 500;
      color: var(--primary-text-color);
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }

    .grid-2 {
      grid-template-columns: repeat(2, 1fr);
    }

    .control-row {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .control-label {
      font-size: 12px;
      color: var(--secondary-text-color);
    }

    ha-textfield,
    ha-select {
      width: 100%;
    }

    ha-switch {
      --mdc-theme-secondary: var(--primary-color);
    }

    .sensor-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }

    .sensor-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .sensor-label {
      font-size: 12px;
      color: var(--secondary-text-color);
    }

    .sensor-value {
      font-size: 14px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--divider-color);
    }

    mwc-button {
      --mdc-theme-primary: var(--primary-color);
    }

    .error-text {
      color: var(--error-color);
      font-size: 12px;
      margin-top: 4px;
    }
  `;

  constructor() {
    super();
    this._data = {};
    this._edited = {};
    this._editingFields = new Set(); // Track which fields are currently being edited
  }

  setConfig(config) {
    if (!config.pid_entity) {
      throw new Error("pid_entity is required");
    }
    this.config = config;
  }

  getCardSize() {
    return 10;
  }

  updated(changedProperties) {
    if (changedProperties.has("hass") || changedProperties.has("config")) {
      // Only update if we're not currently editing (no active edits)
      // This prevents overwriting user input while they're typing
      if (!this._hasEdits()) {
        this._updateData();
      } else {
        // Still update read-only sensor values, but preserve edited values
        this._updateData();
      }
    }
  }

  _updateData() {
    if (!this.hass || !this.config) return;

    const state = this.hass.states[this.config.pid_entity];
    const data = {};

    if (state && state.attributes) {
      const attrs = state.attributes;
      // Only update fields that aren't currently being edited
      if (this._edited.enabled === undefined) {
        data.enabled = attrs.enabled ?? false;
      } else {
        data.enabled = this._data.enabled ?? attrs.enabled ?? false;
      }
      
      if (this._edited.runtime_mode === undefined) {
        data.runtime_mode = attrs.runtime_mode || "AUTO_SP";
      } else {
        data.runtime_mode = this._data.runtime_mode ?? attrs.runtime_mode || "AUTO_SP";
      }
      
      // For number fields, preserve edited values
      const numberFields = ['manual_out', 'manual_sp', 'deadband', 'kp', 'ki', 'kd', 'max_output', 'min_output'];
      for (const field of numberFields) {
        if (this._editingFields.has(field) || this._edited[field] !== undefined) {
          // Keep the edited value - don't overwrite it while user is typing
          data[field] = this._edited[field] ?? this._data[field] ?? attrs[field] ?? null;
        } else {
          // Update from entity state
          data[field] = attrs[field] ?? null;
        }
      }
      
      // Always update read-only sensor values
      data.runtime_modes = attrs.runtime_modes || [
        "AUTO_SP",
        "MANUAL_SP",
        "HOLD",
        "MANUAL_OUT",
      ];
      data.pv_value = attrs.pv_value ?? null;
      data.effective_sp = attrs.effective_sp ?? null;
      data.error = attrs.error ?? null;
      data.output = attrs.output ?? null;
      data.p_term = attrs.p_term ?? null;
      data.i_term = attrs.i_term ?? null;
      data.d_term = attrs.d_term ?? null;
      data.grid_power = attrs.grid_power ?? null;
      data.status = attrs.status || "unknown";
      data.limiter_state = attrs.limiter_state ?? null;
      data.output_pre_rate_limit = attrs.output_pre_rate_limit ?? null;
    }

    this._data = data;
    this.requestUpdate();
  }

  _hasEdits() {
    return Object.keys(this._edited).length > 0;
  }

  _getValue(key) {
    // Always prioritize edited value - this prevents overwriting user input
    if (this._edited[key] !== undefined) {
      return this._edited[key];
    }
    return this._data[key];
  }

  _onEnableChanged(ev) {
    this._edited.enabled = ev.target.checked;
    // Auto-save on change
    this._save();
    this.requestUpdate();
  }

  _onModeChanged(ev) {
    ev.stopPropagation();
    // ha-select uses ev.detail.value, not ev.target.value
    const value = ev.detail?.value || ev.target.value;
    this._edited.runtime_mode = value;
    // Auto-save on change
    this._save();
    this.requestUpdate();
  }

  _onNumberChanged(key, ev) {
    const value = parseFloat(ev.target.value);
    if (!isNaN(value)) {
      this._edited[key] = value;
      this._editingFields.add(key); // Mark as being edited
      // Also update _data immediately so it persists during updates
      if (!this._data) this._data = {};
      this._data[key] = value;
    } else {
      delete this._edited[key];
      this._editingFields.delete(key);
    }
    // Don't call requestUpdate here - let the input field handle its own state
  }

  _onNumberBlur(key, ev) {
    // Mark field as no longer being edited
    this._editingFields.delete(key);
    // Save on blur (when user leaves the field)
    if (this._edited[key] !== undefined) {
      this._save();
    }
    this.requestUpdate();
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

  async _save() {
    if (!this._hasEdits()) return;

    const patch = { ...this._edited };
    
    // Extract device name from status entity ID (e.g., sensor.charger_pid_status -> charger_pid)
    const statusEntity = this.config.pid_entity;
    const deviceName = statusEntity.replace(/^sensor\./, "").replace(/_status$/, "");
    
    try {
      // Update enabled switch
      if (patch.enabled !== undefined) {
        const enabledEntity = `switch.${deviceName}_enabled`;
        await this.hass.callService("switch", patch.enabled ? "turn_on" : "turn_off", {
          entity_id: enabledEntity,
        });
        delete patch.enabled;
      }
      
      // Update runtime mode select
      if (patch.runtime_mode !== undefined) {
        const runtimeModeEntity = `select.${deviceName}_runtime_mode`;
        await this.hass.callService("select", "select_option", {
          entity_id: runtimeModeEntity,
          option: patch.runtime_mode,
        });
        delete patch.runtime_mode;
      }
      
      // Update number entities (kp, ki, kd, deadband, min_output, max_output, manual_out, manual_sp)
      const numberMappings = {
        kp: "kp",
        ki: "ki",
        kd: "kd",
        deadband: "pid_deadband",
        min_output: "min_output",
        max_output: "max_output",
        manual_out: "manual_out_value",
        manual_sp: "manual_sp_value",
      };
      
      for (const [key, entitySuffix] of Object.entries(numberMappings)) {
        if (patch[key] !== undefined) {
          const numberEntity = `number.${deviceName}_${entitySuffix}`;
          await this.hass.callService("number", "set_value", {
            entity_id: numberEntity,
            value: patch[key],
          });
          // Update the data immediately so the UI reflects the change
          this._data[key] = patch[key];
        }
      }
      
      // Clear edits after a delay to allow entity states to update
      // Keep the edited values visible until the entity updates
      setTimeout(() => {
        this._edited = {};
        this._updateData();
      }, 2000);
      
      this.requestUpdate();
    } catch (err) {
      alert(`Error saving: ${err.message || err}`);
      console.error("Error saving PID settings:", err);
    }
  }

  _reset() {
    this._edited = {};
    this.requestUpdate();
  }

  _close() {
    // Try to close the dialog if we're in one
    const dialog = this.closest("ha-dialog");
    if (dialog) {
      dialog.close();
    }
    // If using browser_mod, try to close that way
    if (this.hass && this.hass.callService) {
      try {
        this.hass.callService("browser_mod", "close_popup", {});
      } catch (e) {
        // Ignore if browser_mod not available
      }
    }
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    const enabled = this._getValue("enabled");
    const runtime_mode = this._getValue("runtime_mode");
    const manual_out = this._getValue("manual_out");
    const manual_sp = this._getValue("manual_sp");
    const deadband = this._getValue("deadband");
    const kp = this._getValue("kp");
    const ki = this._getValue("ki");
    const kd = this._getValue("kd");
    const max_output = this._getValue("max_output");
    const min_output = this._getValue("min_output");
    const runtime_modes = this._data.runtime_modes || [];

    return html`
      <ha-card>
        <div class="header">
          <div class="title">PID Controller Editor</div>
        </div>

        <!-- Control Settings -->
        <div class="section">
          <div class="section-title">Control</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Enabled</div>
              <ha-switch
                .checked=${enabled}
                @change=${this._onEnableChanged}
              ></ha-switch>
            </div>

            <div class="control-row">
              <div class="control-label">Runtime Mode</div>
              <ha-select
                .value=${runtime_mode || ""}
                @selected=${this._onModeChanged}
              >
                ${runtime_modes.map(
                  (mode) =>
                    html`<mwc-list-item value="${mode}"
                      >${this._formatMode(mode)}</mwc-list-item
                    >`
                )}
              </ha-select>
            </div>
          </div>
        </div>

        <!-- Manual Values -->
        <div class="section">
          <div class="section-title">Manual Values</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Manual Output</div>
              <ha-textfield
                type="number"
                .value=${manual_out ?? ""}
                @input=${(e) => this._onNumberChanged("manual_out", e)}
                @blur=${(e) => this._onNumberBlur("manual_out", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Manual Setpoint</div>
              <ha-textfield
                type="number"
                .value=${manual_sp ?? ""}
                @input=${(e) => this._onNumberChanged("manual_sp", e)}
                @blur=${(e) => this._onNumberBlur("manual_sp", e)}
                placeholder="—"
              ></ha-textfield>
            </div>
          </div>
        </div>

        <!-- PID Tuning -->
        <div class="section">
          <div class="section-title">PID Tuning</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Kp</div>
              <ha-textfield
                type="number"
                step="0.1"
                .value=${kp ?? ""}
                @input=${(e) => this._onNumberChanged("kp", e)}
                @blur=${(e) => this._onNumberBlur("kp", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Ki</div>
              <ha-textfield
                type="number"
                step="0.01"
                .value=${ki ?? ""}
                @input=${(e) => this._onNumberChanged("ki", e)}
                @blur=${(e) => this._onNumberBlur("ki", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Kd</div>
              <ha-textfield
                type="number"
                step="0.1"
                .value=${kd ?? ""}
                @input=${(e) => this._onNumberChanged("kd", e)}
                @blur=${(e) => this._onNumberBlur("kd", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Deadband</div>
              <ha-textfield
                type="number"
                step="0.1"
                .value=${deadband ?? ""}
                @input=${(e) => this._onNumberChanged("deadband", e)}
                @blur=${(e) => this._onNumberBlur("deadband", e)}
                placeholder="—"
              ></ha-textfield>
            </div>
          </div>
        </div>

        <!-- Output Limits -->
        <div class="section">
          <div class="section-title">Output Limits</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Min Output</div>
              <ha-textfield
                type="number"
                .value=${min_output ?? ""}
                @input=${(e) => this._onNumberChanged("min_output", e)}
                @blur=${(e) => this._onNumberBlur("min_output", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Max Output</div>
              <ha-textfield
                type="number"
                .value=${max_output ?? ""}
                @input=${(e) => this._onNumberChanged("max_output", e)}
                @blur=${(e) => this._onNumberBlur("max_output", e)}
                placeholder="—"
              ></ha-textfield>
            </div>
          </div>
        </div>

        <!-- Sensor Values (Read-only) -->
        <div class="section">
          <div class="section-title">Current Values</div>
          <div class="sensor-grid">
            <div class="sensor-item">
              <div class="sensor-label">Status</div>
              <div class="sensor-value">${this._data.status || "—"}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">PV</div>
              <div class="sensor-value">${this._formatValue(this._data.pv_value)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">SP</div>
              <div class="sensor-value">${this._formatValue(this._data.effective_sp)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">Error</div>
              <div class="sensor-value">${this._formatValue(this._data.error)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">Output</div>
              <div class="sensor-value">${this._formatValue(this._data.output)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">P Term</div>
              <div class="sensor-value">${this._formatValue(this._data.p_term)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">I Term</div>
              <div class="sensor-value">${this._formatValue(this._data.i_term)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">D Term</div>
              <div class="sensor-value">${this._formatValue(this._data.d_term)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">Grid Power</div>
              <div class="sensor-value">${this._formatValue(this._data.grid_power)}</div>
            </div>
            <div class="sensor-item">
              <div class="sensor-label">Limiter State</div>
              <div class="sensor-value">${this._data.limiter_state || "—"}</div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="actions">
          <mwc-button
            outlined
            label="Reset"
            @click=${this._reset}
            ?disabled=${!this._hasEdits()}
          ></mwc-button>
          <mwc-button
            raised
            label="Save"
            @click=${this._save}
            ?disabled=${!this._hasEdits()}
          ></mwc-button>
          <mwc-button
            outlined
            label="Close"
            @click=${this._close}
          ></mwc-button>
        </div>
      </ha-card>
    `;
  }
}

customElements.define("pid-controller-popup", PIDControllerPopup);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "pid-controller-popup",
  name: "PID Controller Popup",
  description: "Full editor popup for PID controller settings",
  preview: false,
});

