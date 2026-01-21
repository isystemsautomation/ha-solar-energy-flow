import { LitElement, html, css } from "lit";

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
      position: relative;
    }

    ha-card {
      padding: 16px;
    }

    .header {
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--divider-color);
      display: flex;
      justify-content: flex-start;
      align-items: center;
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

    .graph-container {
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--divider-color);
      min-height: 200px;
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
    this._edited = {};
    this._editingFields = new Set();
    this._savedFields = new Map();
    this._updateInterval = null;
    this._lastFullUpdate = 0;
    this._stateChangedUnsub = null;
    this._graphInterval = null;
    this._resizeObserver = null;
    this._canvas = null;
    this._chart = null;
    this._graphInFlight = false;
    this._graphUpdateTimeout = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._loadChartJS();
    this._startLiveUpdates();
    this._subscribeToStateChanges();
    setTimeout(() => this._updateGraph(), 300);
    this._graphInterval = setInterval(() => this._updateGraph(), 30000);
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
    super.disconnectedCallback();
    if (this._updateInterval) {
      clearInterval(this._updateInterval);
      this._updateInterval = null;
    }
    if (this._stateChangedUnsub) {
      this._stateChangedUnsub();
      this._stateChangedUnsub = null;
    }
    if (this._graphInterval) {
      clearInterval(this._graphInterval);
      this._graphInterval = null;
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    if (this._graphUpdateTimeout) {
      clearTimeout(this._graphUpdateTimeout);
    }
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }

  _subscribeToStateChanges() {
    if (!this.hass || !this.config) return;
    
    if (this._stateChangedUnsub) {
      this._stateChangedUnsub();
      this._stateChangedUnsub = null;
    }
    
    const entityId = this.config.pid_entity;
    const handleStateChanged = (ev) => {
      if (ev.detail && ev.detail.entity_id === entityId) {
        this._updateReadOnlyValues();
        this._checkEntityStateChanges();
      }
    };
    
    if (this.hass.subscribeEvents) {
      this._stateChangedUnsub = this.hass.subscribeEvents(handleStateChanged, "state_changed");
    } else if (this.hass.connection && this.hass.connection.addEventListener) {
      this.hass.connection.addEventListener("state_changed", handleStateChanged);
      this._stateChangedUnsub = () => {
        if (this.hass && this.hass.connection && this.hass.connection.removeEventListener) {
          this.hass.connection.removeEventListener("state_changed", handleStateChanged);
        }
      };
    }
  }

  _startLiveUpdates() {
    if (this._updateInterval) {
      clearInterval(this._updateInterval);
      this._updateInterval = null;
    }
    if (!this.hass || !this.config) return;
    
    this._updateReadOnlyValues();
    
    this._updateInterval = setInterval(() => {
      if (this.hass && this.config && this._editingFields.size === 0) {
        const state = this.hass.states[this.config.pid_entity];
        if (state) {
          this._updateReadOnlyValues();
          this._checkEntityStateChanges();
          if (!this._lastFullUpdate || (Date.now() - this._lastFullUpdate > 2000)) {
            this._updateData();
            this._lastFullUpdate = Date.now();
          }
        }
      }
    }, 500);
  }

  _checkEntityStateChanges() {
    if (!this.hass || !this.config) return;
    if (this._editingFields.size > 0) return;
    
    const state = this.hass.states[this.config.pid_entity];
    if (!state?.attributes) return;
    
    const attrs = state.attributes;
    let hasChanges = false;
    const now = Date.now();
    const SAVE_TIMEOUT = 30000;
    const runtimeMode = attrs.runtime_mode || "AUTO_SP";
    const isManualOutMode = runtimeMode === "MANUAL_OUT";
    const isManualSpMode = runtimeMode === "MANUAL_SP";
    
    const editableFields = ['manual_out', 'manual_sp', 'deadband', 'kp', 'ki', 'kd', 'max_output', 'min_output', 'enabled', 'runtime_mode', 'grid_limiter_enabled', 'rate_limiter_enabled', 'grid_limiter_limit', 'rate_limit'];
    for (const field of editableFields) {
      if (this._editingFields.has(field)) continue;
      
      const savedTime = this._savedFields.get(field);
      if (savedTime && (now - savedTime <= SAVE_TIMEOUT)) {
        let entityValue = attrs[field];
        if (field === 'enabled' || field === 'grid_limiter_enabled' || field === 'rate_limiter_enabled') {
          const switchEntityId = this._findEntityId("switch", field === 'enabled' ? "enabled" : field === 'grid_limiter_enabled' ? "grid_limiter_enabled" : "rate_limiter");
          const switchEntityState = this.hass?.states[switchEntityId];
          entityValue = switchEntityState?.state === "on";
        } else if (field === 'runtime_mode') {
          entityValue = attrs.runtime_mode || "AUTO_SP";
        } else if (field === 'grid_limiter_limit' || field === 'rate_limit') {
          const numberEntityId = this._findEntityId("number", field === 'grid_limiter_limit' ? "grid_limiter_limit" : "rate_limit");
          const numberEntityState = this.hass?.states[numberEntityId];
          entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : null;
        } else if (field === 'manual_sp') {
          if (isManualSpMode) {
            const numberEntityId = this._findEntityId("number", "manual_sp_value");
            const numberEntityState = this.hass?.states[numberEntityId];
            entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : (attrs[field] ?? null);
          } else {
            entityValue = attrs[field] ?? null;
          }
        } else if (field === 'manual_out') {
          if (isManualOutMode) {
            const numberEntityId = this._findEntityId("number", "manual_out_value");
            const numberEntityState = this.hass?.states[numberEntityId];
            entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : (attrs[field] ?? null);
          } else {
            entityValue = attrs[field] ?? null;
          }
        }
        
        const savedValue = this._data[field];
        const matches = (field === 'enabled' || field === 'runtime_mode' || field === 'grid_limiter_enabled' || field === 'rate_limiter_enabled') 
          ? entityValue === savedValue
          : Math.abs((entityValue ?? 0) - (savedValue ?? 0)) < 0.01;
        
        if (matches) {
          this._savedFields.delete(field);
        }
        continue;
      }
      
      let entityValue = attrs[field];
      if (field === 'enabled' || field === 'grid_limiter_enabled' || field === 'rate_limiter_enabled') {
        const switchEntityId = this._findEntityId("switch", field === 'enabled' ? "enabled" : field === 'grid_limiter_enabled' ? "grid_limiter_enabled" : "rate_limiter");
        const switchEntityState = this.hass?.states[switchEntityId];
        entityValue = switchEntityState?.state === "on";
      } else if (field === 'runtime_mode') {
        entityValue = attrs.runtime_mode || "AUTO_SP";
      } else if (field === 'grid_limiter_limit' || field === 'rate_limit') {
        const numberEntityId = this._findEntityId("number", field === 'grid_limiter_limit' ? "grid_limiter_limit" : "rate_limit");
        const numberEntityState = this.hass?.states[numberEntityId];
        entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : null;
      } else if (field === 'manual_sp') {
        if (isManualSpMode) {
          const numberEntityId = this._findEntityId("number", "manual_sp_value");
          const numberEntityState = this.hass?.states[numberEntityId];
          entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : (attrs[field] ?? null);
        } else {
          entityValue = attrs[field] ?? null;
        }
      } else if (field === 'manual_out') {
        if (isManualOutMode) {
          const numberEntityId = this._findEntityId("number", "manual_out_value");
          const numberEntityState = this.hass?.states[numberEntityId];
          entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : (attrs[field] ?? null);
        } else {
          entityValue = attrs[field] ?? null;
        }
      }
      
      const currentValue = this._data[field];
      if (field === 'enabled' || field === 'runtime_mode' || field === 'grid_limiter_enabled' || field === 'rate_limiter_enabled') {
        if (entityValue !== currentValue) {
          this._data[field] = entityValue;
          hasChanges = true;
        }
      } else {
        if (Math.abs((entityValue ?? 0) - (currentValue ?? 0)) > 0.01) {
          this._data[field] = entityValue;
          hasChanges = true;
        }
      }
    }
    
    if (hasChanges) {
      this.requestUpdate();
    }
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
      if (this._editingFields.size === 0) {
      this._updateData();
      }
      if (this.hass && this.config) {
        if (!this._updateInterval) {
          this._startLiveUpdates();
        }
        this._updateReadOnlyValues();
      }
    }
    if (changedProperties.has("hass") && this._editingFields.size === 0) {
      this._updateReadOnlyValues();
      this._checkEntityStateChanges();
      this._scheduleGraphUpdate(800);
    }
  }

  _updateData() {
    if (!this.hass || !this.config) return;
    if (this._editingFields.size > 0) return;

    const state = this.hass.states[this.config.pid_entity];
    if (!state) return;
    
    const data = { ...this._data };
    const SAVE_TIMEOUT = 30000;

    if (state?.attributes) {
      const attrs = state.attributes;
      const now = Date.now();
      
      if (this._edited.enabled === undefined) {
        const savedTime = this._savedFields.get("enabled");
        if (!savedTime || (now - savedTime > SAVE_TIMEOUT)) {
          if (!savedTime || attrs.enabled === this._data.enabled) {
      data.enabled = attrs.enabled ?? false;
            this._savedFields.delete("enabled");
          }
        }
      } else {
        data.enabled = this._data.enabled ?? attrs.enabled ?? false;
      }
      
      if (this._edited.runtime_mode === undefined) {
        const savedTime = this._savedFields.get("runtime_mode");
        if (!savedTime || (now - savedTime > SAVE_TIMEOUT)) {
          if (!savedTime || attrs.runtime_mode === this._data.runtime_mode) {
      data.runtime_mode = attrs.runtime_mode || "AUTO_SP";
            this._savedFields.delete("runtime_mode");
          }
        }
      } else {
        data.runtime_mode = this._data.runtime_mode ?? (attrs.runtime_mode || "AUTO_SP");
      }
      
      if (this._edited.grid_limiter_enabled === undefined) {
        const savedTime = this._savedFields.get("grid_limiter_enabled");
        if (!savedTime || (now - savedTime > SAVE_TIMEOUT)) {
          const switchEntityId = this._findEntityId("switch", "grid_limiter_enabled");
          const switchEntityState = this.hass?.states[switchEntityId];
          const entityValue = switchEntityState?.state === "on";
          if (!savedTime || entityValue === this._data.grid_limiter_enabled) {
            data.grid_limiter_enabled = entityValue;
            this._savedFields.delete("grid_limiter_enabled");
          }
        } else {
          data.grid_limiter_enabled = this._data.grid_limiter_enabled ?? false;
        }
      } else {
        data.grid_limiter_enabled = this._data.grid_limiter_enabled ?? false;
      }
      
      if (this._edited.rate_limiter_enabled === undefined) {
        const savedTime = this._savedFields.get("rate_limiter_enabled");
        if (!savedTime || (now - savedTime > SAVE_TIMEOUT)) {
          const switchEntityId = this._findEntityId("switch", "rate_limiter");
          const switchEntityState = this.hass?.states[switchEntityId];
          const entityValue = switchEntityState?.state === "on";
          if (!savedTime || entityValue === this._data.rate_limiter_enabled) {
            data.rate_limiter_enabled = entityValue;
            this._savedFields.delete("rate_limiter_enabled");
          }
        } else {
          data.rate_limiter_enabled = this._data.rate_limiter_enabled ?? false;
        }
      } else {
        data.rate_limiter_enabled = this._data.rate_limiter_enabled ?? false;
      }
      
      const numberFields = ['manual_out', 'manual_sp', 'deadband', 'kp', 'ki', 'kd', 'max_output', 'min_output', 'grid_limiter_limit', 'rate_limit'];
      for (const field of numberFields) {
        if (this._editingFields.has(field)) {
          data[field] = this._edited[field] !== undefined ? this._edited[field] : this._data[field];
          continue;
        }
        if (this._edited[field] !== undefined) {
          data[field] = this._edited[field];
          continue;
        } else {
          const savedTime = this._savedFields.get(field);
          if (savedTime && (now - savedTime <= SAVE_TIMEOUT)) {
            let entityValue = attrs[field] ?? null;
            if (field === 'grid_limiter_limit' || field === 'rate_limit') {
              const numberEntityId = this._findEntityId("number", field === 'grid_limiter_limit' ? "grid_limiter_limit" : "rate_limit");
              const numberEntityState = this.hass?.states[numberEntityId];
              entityValue = numberEntityState?.state ? parseFloat(numberEntityState.state) : null;
            }
            const savedValue = this._data[field] ?? null;
            if (Math.abs((entityValue ?? 0) - (savedValue ?? 0)) < 0.01) {
              data[field] = entityValue;
              this._savedFields.delete(field);
            } else {
              data[field] = savedValue;
            }
          } else {
            if (field === 'grid_limiter_limit' || field === 'rate_limit') {
              const numberEntityId = this._findEntityId("number", field === 'grid_limiter_limit' ? "grid_limiter_limit" : "rate_limit");
              const numberEntityState = this.hass?.states[numberEntityId];
              data[field] = numberEntityState?.state ? parseFloat(numberEntityState.state) : null;
            } else {
              data[field] = attrs[field] ?? null;
            }
            if (savedTime) {
              this._savedFields.delete(field);
            }
          }
        }
      }
      
      data.runtime_modes = attrs.runtime_modes || ["AUTO_SP", "MANUAL_SP", "HOLD", "MANUAL_OUT"];
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

  _updateReadOnlyValues() {
    if (!this.hass || !this.config) return;

    const state = this.hass.states[this.config.pid_entity];
    if (!state?.attributes) return;

    const attrs = state.attributes;
    let hasChanges = false;
    
    const compareValue = (oldVal, newVal) => {
      if (oldVal === newVal) return false;
      if (oldVal === null || oldVal === undefined) return newVal !== null && newVal !== undefined;
      if (newVal === null || newVal === undefined) return true;
      if (typeof oldVal === "number" && typeof newVal === "number") {
        return Math.abs(oldVal - newVal) > 0.01;
      }
      return String(oldVal) !== String(newVal);
    };
    
    const newValues = {
      pv_value: attrs.pv_value ?? null,
      effective_sp: attrs.effective_sp ?? null,
      error: attrs.error ?? null,
      output: attrs.output ?? null,
      p_term: attrs.p_term ?? null,
      i_term: attrs.i_term ?? null,
      d_term: attrs.d_term ?? null,
      grid_power: attrs.grid_power ?? null,
      status: attrs.status || "unknown",
      limiter_state: attrs.limiter_state ?? null,
      output_pre_rate_limit: attrs.output_pre_rate_limit ?? null,
    };
    
    if (compareValue(this._data.pv_value, newValues.pv_value)) {
      this._data.pv_value = newValues.pv_value;
      hasChanges = true;
    }
    if (compareValue(this._data.effective_sp, newValues.effective_sp)) {
      this._data.effective_sp = newValues.effective_sp;
      hasChanges = true;
    }
    if (compareValue(this._data.error, newValues.error)) {
      this._data.error = newValues.error;
      hasChanges = true;
    }
    if (compareValue(this._data.output, newValues.output)) {
      this._data.output = newValues.output;
      hasChanges = true;
    }
    if (compareValue(this._data.p_term, newValues.p_term)) {
      this._data.p_term = newValues.p_term;
      hasChanges = true;
    }
    if (compareValue(this._data.i_term, newValues.i_term)) {
      this._data.i_term = newValues.i_term;
      hasChanges = true;
    }
    if (compareValue(this._data.d_term, newValues.d_term)) {
      this._data.d_term = newValues.d_term;
      hasChanges = true;
    }
    if (compareValue(this._data.grid_power, newValues.grid_power)) {
      this._data.grid_power = newValues.grid_power;
      hasChanges = true;
    }
    if (this._data.status !== newValues.status) {
      this._data.status = newValues.status;
      hasChanges = true;
    }
    if (this._data.limiter_state !== newValues.limiter_state) {
      this._data.limiter_state = newValues.limiter_state;
      hasChanges = true;
    }
    if (compareValue(this._data.output_pre_rate_limit, newValues.output_pre_rate_limit)) {
      this._data.output_pre_rate_limit = newValues.output_pre_rate_limit;
      hasChanges = true;
    }
    
    if (hasChanges) {
      this.requestUpdate();
    }
  }

  _hasEdits() {
    return Object.keys(this._edited).length > 0;
  }

  _getValue(key) {
    if (this._editingFields.has(key) && this._edited[key] !== undefined) {
      return this._edited[key];
    }
    if (this._editingFields.has(key)) {
      return this._data[key] ?? "";
    }
    return this._edited[key] !== undefined ? this._edited[key] : this._data[key];
  }

  _onEnableChanged(ev) {
    this._edited.enabled = ev.target.checked;
    this._save();
    this.requestUpdate();
  }

  _onGridLimiterChanged(ev) {
    this._edited.grid_limiter_enabled = ev.target.checked;
    this._save();
    this.requestUpdate();
  }

  _onRateLimiterChanged(ev) {
    this._edited.rate_limiter_enabled = ev.target.checked;
    this._save();
    this.requestUpdate();
  }

  _onModeChanged(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    ev.stopImmediatePropagation();
    
    const value = ev.detail?.value || ev.target?.value || ev.target?.selected?.value;
    if (!value) return;
    
    this._edited.runtime_mode = value;
    this._save();
    this.requestUpdate();
  }

  _onNumberChanged(key, ev) {
    const inputValue = ev.target.value;
    this._editingFields.add(key);
    
    if (inputValue === "" || inputValue === "-" || inputValue === "." || inputValue === "-.") {
      this._edited[key] = null;
      this._data[key] = null;
    } else {
      const value = parseFloat(inputValue);
      if (!isNaN(value)) {
        this._edited[key] = value;
        this._data[key] = value;
      } else {
        const prevValue = this._getValue(key);
        ev.target.value = prevValue !== null && prevValue !== undefined ? String(prevValue) : "";
        return;
      }
    }
    
    this.requestUpdate();
  }

  async _onNumberBlur(key, ev) {
    if (this._edited[key] !== undefined) {
      await this._save();
    }
    this._editingFields.delete(key);
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

  _findEntityId(domain, suffix) {
    const statusEntity = this.config.pid_entity;
    const deviceName = statusEntity.replace(/^sensor\./, "").replace(/_status$/, "");
    
    const suffixMap = {
      "manual_sp_value": "manual_sp",
      "manual_out_value": "manual_out",
      "grid_limiter_limit": "grid_limiter_limit",
      "rate_limit": "rate_limit",
    };
    
    const entityName = suffixMap[suffix] || suffix;
    const candidateId = `${domain}.${deviceName}_${entityName}`;
    
    if (this.hass.states[candidateId]) {
      return candidateId;
    }
    
    const prefix = `${domain}.${deviceName}`;
    const possibleEndings = [`_${entityName}`, `_${suffix}`, `_${suffix.replace(/_enabled$/, "")}`, `_${suffix.replace(/_enabled$/, "_enabled")}`];
    
    for (const entityId in this.hass.states) {
      if (entityId.startsWith(prefix)) {
        for (const ending of possibleEndings) {
          if (entityId.endsWith(ending)) {
            return entityId;
          }
        }
      }
    }
    
    return candidateId;
  }

  async _save() {
    if (!this._hasEdits()) return;

    const patch = { ...this._edited };
    const numberMappings = {
      kp: "kp",
      ki: "ki",
      kd: "kd",
      deadband: "pid_deadband",
      min_output: "min_output",
      max_output: "max_output",
      manual_out: "manual_out_value",
      manual_sp: "manual_sp_value",
      grid_limiter_limit: "grid_limiter_limit",
      rate_limit: "rate_limit",
    };
    
    try {
      const now = Date.now();
      
      if (patch.enabled !== undefined) {
        const entityId = this._findEntityId("switch", "enabled");
        await this.hass.callService("switch", patch.enabled ? "turn_on" : "turn_off", {
          entity_id: entityId,
        });
        this._data.enabled = patch.enabled;
        this._savedFields.set("enabled", now);
        delete patch.enabled;
      }
      
      if (patch.runtime_mode !== undefined) {
        const entityId = this._findEntityId("select", "runtime_mode");
        await this.hass.callService("select", "select_option", {
          entity_id: entityId,
          option: patch.runtime_mode,
        });
        this._data.runtime_mode = patch.runtime_mode;
        this._savedFields.set("runtime_mode", now);
        delete patch.runtime_mode;
      }
      
      if (patch.grid_limiter_enabled !== undefined) {
        const entityId = this._findEntityId("switch", "grid_limiter_enabled");
        if (!entityId || !this.hass.states[entityId]) {
          alert(`Grid limiter switch entity not found: ${entityId || "unknown"}`);
          throw new Error(`Grid limiter switch entity not found`);
        }
        await this.hass.callService("switch", patch.grid_limiter_enabled ? "turn_on" : "turn_off", {
          entity_id: entityId,
        });
        await new Promise(resolve => setTimeout(resolve, 200));
        this._data.grid_limiter_enabled = patch.grid_limiter_enabled;
        this._savedFields.set("grid_limiter_enabled", now);
        delete this._edited.grid_limiter_enabled;
        delete patch.grid_limiter_enabled;
      }
      
      if (patch.rate_limiter_enabled !== undefined) {
        const entityId = this._findEntityId("switch", "rate_limiter");
        await this.hass.callService("switch", patch.rate_limiter_enabled ? "turn_on" : "turn_off", {
          entity_id: entityId,
        });
        await new Promise(resolve => setTimeout(resolve, 200));
        this._data.rate_limiter_enabled = patch.rate_limiter_enabled;
        this._savedFields.set("rate_limiter_enabled", now);
        delete this._edited.rate_limiter_enabled;
        delete patch.rate_limiter_enabled;
      }
      
      for (const [key, entitySuffix] of Object.entries(numberMappings)) {
        if (patch[key] !== undefined) {
          const entityId = this._findEntityId("number", entitySuffix);
          try {
            await this.hass.callService("number", "set_value", {
              entity_id: entityId,
              value: patch[key],
            });
            
            await new Promise(resolve => setTimeout(resolve, 200));
            
            this._data[key] = patch[key];
            this._savedFields.set(key, now);
            delete this._edited[key];
          } catch (err) {
            alert(`Error saving ${key}: ${err.message || err}`);
            throw err;
          }
        }
      }
      
      this._edited = {};
      this.requestUpdate();
    } catch (err) {
      if (!err.message || !err.message.includes("Error saving")) {
        alert(`Error saving: ${err.message || err}`);
      }
    }
  }

  _reset() {
    this._edited = {};
    this.requestUpdate();
  }

  _close() {
    const dialog = this.closest("ha-dialog");
    if (dialog) {
      dialog.close();
    }
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

    const container = this.shadowRoot?.getElementById("popup-graph-container");
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
      const container = this.shadowRoot?.getElementById("popup-graph-container");
      if (container && !this._chart) {
        const errorMsg = err?.message || (typeof err === 'string' ? err : JSON.stringify(err));
        container.innerHTML = `<div style='padding: 8px; color: var(--error-color, red); font-size: 12px;'>Graph error: ${errorMsg}</div>`;
      }
    } finally {
      this._graphInFlight = false;
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
    const grid_limiter_enabled = this._getValue("grid_limiter_enabled");
    const rate_limiter_enabled = this._getValue("rate_limiter_enabled");
    const grid_limiter_limit = this._getValue("grid_limiter_limit");
    const rate_limit = this._getValue("rate_limit");
    const runtime_modes = this._data.runtime_modes || [];

    return html`
      <ha-card>
        <div class="header">
          <div class="title">PID Controller Editor</div>
        </div>

        <div class="graph-container" id="popup-graph-container"></div>

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
                @selected=${(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  this._onModeChanged(e);
                }}
                @closed=${(e) => e.stopPropagation()}
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

        <div class="section">
          <div class="section-title">Manual Values</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Manual Output</div>
              <ha-textfield
                type="number"
                .value=${this._editingFields.has("manual_out") && this._edited.manual_out !== undefined 
                  ? String(this._edited.manual_out) 
                  : String(manual_out ?? "")}
                @input=${(e) => {
                  e.stopPropagation();
                  this._onNumberChanged("manual_out", e);
                }}
                @blur=${(e) => {
                  e.stopPropagation();
                  this._onNumberBlur("manual_out", e);
                }}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Manual Setpoint</div>
              <ha-textfield
                type="number"
                .value=${this._editingFields.has("manual_sp") && this._edited.manual_sp !== undefined 
                  ? String(this._edited.manual_sp) 
                  : String(manual_sp ?? "")}
                @input=${(e) => {
                  e.stopPropagation();
                  this._onNumberChanged("manual_sp", e);
                }}
                @blur=${(e) => {
                  e.stopPropagation();
                  this._onNumberBlur("manual_sp", e);
                }}
                placeholder="—"
              ></ha-textfield>
            </div>
          </div>
        </div>

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

        <div class="section">
          <div class="section-title">Limiters</div>
          <div class="grid grid-2">
            <div class="control-row">
              <div class="control-label">Grid Limiter</div>
              <ha-switch
                .checked=${grid_limiter_enabled}
                @change=${this._onGridLimiterChanged}
              ></ha-switch>
            </div>

            <div class="control-row">
              <div class="control-label">Grid Limiter Limit</div>
              <ha-textfield
                type="number"
                .value=${grid_limiter_limit ?? ""}
                @input=${(e) => this._onNumberChanged("grid_limiter_limit", e)}
                @blur=${(e) => this._onNumberBlur("grid_limiter_limit", e)}
                placeholder="—"
              ></ha-textfield>
            </div>

            <div class="control-row">
              <div class="control-label">Rate Limiter</div>
              <ha-switch
                .checked=${rate_limiter_enabled}
                @change=${this._onRateLimiterChanged}
              ></ha-switch>
            </div>

            <div class="control-row">
              <div class="control-label">Rate Limit</div>
              <ha-textfield
                type="number"
                .value=${rate_limit ?? ""}
                @input=${(e) => this._onNumberChanged("rate_limit", e)}
                @blur=${(e) => this._onNumberBlur("rate_limit", e)}
                placeholder="—"
              ></ha-textfield>
            </div>
          </div>
        </div>

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


