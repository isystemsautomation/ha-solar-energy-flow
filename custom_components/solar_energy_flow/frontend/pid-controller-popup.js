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
  }

  connectedCallback() {
    super.connectedCallback();
    this._startLiveUpdates();
    this._subscribeToStateChanges();
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
  }

  _subscribeToStateChanges() {
    if (!this.hass || !this.config) return;
    
    // Unsubscribe from previous subscription if any
    if (this._stateChangedUnsub) {
      this._stateChangedUnsub();
      this._stateChangedUnsub = null;
    }
    
    // Subscribe to state_changed events for our entity using Home Assistant API
    const entityId = this.config.pid_entity;
    
    const handleStateChanged = (ev) => {
      if (ev.detail && ev.detail.entity_id === entityId) {
        // Entity state changed - force immediate update
        this._updateReadOnlyValues();
        this._checkEntityStateChanges();
        // Also do a full update after a short delay to ensure all attributes are fresh
        setTimeout(() => {
          if (!this._editingFields.size) {
            this._updateData();
          }
        }, 100);
      }
    };
    
    // Try to use hass.subscribeEvents if available (Home Assistant API)
    if (this.hass.subscribeEvents) {
      this._stateChangedUnsub = this.hass.subscribeEvents(handleStateChanged, "state_changed");
    } else if (this.hass.connection && this.hass.connection.addEventListener) {
      // Fallback: use connection event listener
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
    
    // Initial update immediately
    this._updateReadOnlyValues();
    
    // Update every 300ms for very responsive updates
    this._updateInterval = setInterval(() => {
      if (this.hass && this.config) {
        // Force update by checking hass state directly
        const state = this.hass.states[this.config.pid_entity];
        if (state) {
          // Always update read-only values (PV, SP, Error, Output, etc.)
          // This is critical - these values change frequently
          this._updateReadOnlyValues();
          // Also check if entity attributes changed for editable fields (in case backend updated them)
          this._checkEntityStateChanges();
          // Periodically do a full data update to catch any missed changes
          // Do this less frequently to avoid overwriting user edits
          if (!this._lastFullUpdate || (Date.now() - this._lastFullUpdate > 1500)) {
            // Only do full update if not actively editing
            if (this._editingFields.size === 0) {
              this._updateData();
              this._lastFullUpdate = Date.now();
            }
          }
        }
      }
    }, 300);
  }

  _checkEntityStateChanges() {
    if (!this.hass || !this.config) return;
    
    const state = this.hass.states[this.config.pid_entity];
    if (!state?.attributes) return;
    
    const attrs = state.attributes;
    let hasChanges = false;
    
    // Check if editable values changed on the entity (e.g., manual_sp was updated by another source)
    // Only update if we're not currently editing and haven't recently saved
    const now = Date.now();
    const SAVE_TIMEOUT = 10000; // Increased timeout to 10 seconds to prevent overwriting recently saved values
    
    // Check manual_sp specifically
    if (!this._editingFields.has("manual_sp")) {
      const savedTime = this._savedFields.get("manual_sp");
      if (savedTime && (now - savedTime <= SAVE_TIMEOUT)) {
        // Recently saved - only update if entity state matches what we saved
        const entityValue = attrs.manual_sp ?? null;
        const savedValue = this._data.manual_sp ?? null;
        // If entity matches our saved value, it's confirmed - we can clear the saved flag
        if (Math.abs((entityValue ?? 0) - (savedValue ?? 0)) < 0.01) {
          this._savedFields.delete("manual_sp");
        }
        // Otherwise, keep our saved value and don't overwrite - DO NOT UPDATE
        // Skip to next field - don't update manual_sp
      } else if (!savedTime || (now - savedTime > SAVE_TIMEOUT)) {
        // Not recently saved, or timeout expired - update from entity
        const entityValue = attrs.manual_sp ?? null;
        const currentValue = this._data.manual_sp ?? null;
        if (Math.abs((entityValue ?? 0) - (currentValue ?? 0)) > 0.01) {
          console.log(`manual_sp updating from entity (timeout expired): ${currentValue} -> ${entityValue}`);
          this._data.manual_sp = entityValue;
          hasChanges = true;
        }
      }
    }
    
    // Similar checks for other editable fields that might be updated externally
    const editableFields = ['manual_out', 'deadband', 'kp', 'ki', 'kd', 'max_output', 'min_output', 'enabled', 'runtime_mode'];
    for (const field of editableFields) {
      if (this._editingFields.has(field)) continue;
      
      const savedTime = this._savedFields.get(field);
      if (savedTime && (now - savedTime <= SAVE_TIMEOUT)) {
        // Recently saved - only update if entity state matches what we saved
        let entityValue = attrs[field];
        if (field === 'enabled') {
          entityValue = attrs.enabled ?? false;
        } else if (field === 'runtime_mode') {
          entityValue = attrs.runtime_mode || "AUTO_SP";
        } else {
          entityValue = attrs[field] ?? null;
        }
        
        const savedValue = this._data[field];
        let matches = false;
        if (field === 'enabled' || field === 'runtime_mode') {
          matches = entityValue === savedValue;
        } else {
          matches = Math.abs((entityValue ?? 0) - (savedValue ?? 0)) < 0.01;
        }
        
        if (matches) {
          // Entity matches our saved value - confirmed, clear the saved flag
          this._savedFields.delete(field);
        }
        // Otherwise, keep our saved value and don't overwrite
        continue;
      }
      
      // Not recently saved, or timeout expired - update from entity
      let entityValue = attrs[field];
      if (field === 'enabled') {
        entityValue = attrs.enabled ?? false;
      } else if (field === 'runtime_mode') {
        entityValue = attrs.runtime_mode || "AUTO_SP";
      } else {
        entityValue = attrs[field] ?? null;
      }
      
      const currentValue = this._data[field];
      if (field === 'enabled' || field === 'runtime_mode') {
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
      this._updateData();
      if (this.hass && this.config) {
        if (!this._updateInterval) {
          this._startLiveUpdates();
        }
        // Always force an immediate update when hass/config changes
        this._updateReadOnlyValues();
      }
    }
    // Also update when hass changes (entity state updates)
    if (changedProperties.has("hass")) {
      this._updateReadOnlyValues();
      this._checkEntityStateChanges();
    }
  }

  _updateData() {
    if (!this.hass || !this.config) return;

    const state = this.hass.states[this.config.pid_entity];
    if (!state) return;
    
    const data = { ...this._data };
    const SAVE_TIMEOUT = 10000; // Increased timeout to 10 seconds to prevent overwriting recently saved values

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
      
      const numberFields = ['manual_out', 'manual_sp', 'deadband', 'kp', 'ki', 'kd', 'max_output', 'min_output'];
      for (const field of numberFields) {
        if (this._editingFields.has(field)) {
          // Currently being edited - keep edited value
          data[field] = this._edited[field] ?? this._data[field] ?? attrs[field] ?? null;
        } else if (this._edited[field] !== undefined) {
          // Has unsaved edits - keep edited value
          data[field] = this._edited[field];
        } else {
          // No edits - check if recently saved
          const savedTime = this._savedFields.get(field);
          if (savedTime && (now - savedTime <= SAVE_TIMEOUT)) {
            // Recently saved - keep our saved value, don't overwrite from entity
            // Only update if entity state matches what we saved (confirmation)
            const entityValue = attrs[field] ?? null;
            const savedValue = this._data[field] ?? null;
            if (Math.abs((entityValue ?? 0) - (savedValue ?? 0)) < 0.01) {
              // Entity matches - confirmed, we can clear the saved flag
              data[field] = entityValue;
              this._savedFields.delete(field);
            } else {
              // Entity doesn't match yet - keep our saved value
              data[field] = savedValue;
            }
          } else {
            // Not recently saved, or timeout expired - update from entity
            data[field] = attrs[field] ?? null;
            if (savedTime) {
              this._savedFields.delete(field);
            }
          }
        }
      }
      
      data.runtime_modes = attrs.runtime_modes || ["AUTO_SP", "MANUAL_SP", "HOLD", "MANUAL_OUT"];
      // Always update read-only values from entity state
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

    // Always read the latest state directly from hass - don't cache
    const state = this.hass.states[this.config.pid_entity];
    if (!state?.attributes) {
      console.debug("PID Popup: No state/attributes for", this.config.pid_entity);
      return;
    }

    const attrs = state.attributes;
    let hasChanges = false;
    
    // Compare values with proper type handling
    const compareValue = (oldVal, newVal) => {
      if (oldVal === newVal) return false;
      if (oldVal === null || oldVal === undefined) return newVal !== null && newVal !== undefined;
      if (newVal === null || newVal === undefined) return true;
      if (typeof oldVal === "number" && typeof newVal === "number") {
        return Math.abs(oldVal - newVal) > 0.01;
      }
      return String(oldVal) !== String(newVal);
    };
    
    // Always update these values - they're read-only and should reflect current state
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
    
    // Check for changes
    if (compareValue(this._data.pv_value, newValues.pv_value)) {
      this._data.pv_value = newValues.pv_value;
      hasChanges = true;
    }
    if (compareValue(this._data.effective_sp, newValues.effective_sp)) {
      console.log("PID Popup: SP changed", this._data.effective_sp, "->", newValues.effective_sp);
      this._data.effective_sp = newValues.effective_sp;
      hasChanges = true;
    } else if (this._data.effective_sp !== newValues.effective_sp && newValues.effective_sp !== null) {
      // Force update even if compareValue didn't detect change (might be precision issue)
      console.log("PID Popup: SP force update", this._data.effective_sp, "->", newValues.effective_sp);
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
    
    // Always request update - force re-render to show latest values
    // Even if no changes detected, ensure UI is in sync with entity state
    this.requestUpdate();
  }

  _hasEdits() {
    return Object.keys(this._edited).length > 0;
  }

  _getValue(key) {
    return this._edited[key] !== undefined ? this._edited[key] : this._data[key];
  }

  _onEnableChanged(ev) {
    this._edited.enabled = ev.target.checked;
    this._save();
    this.requestUpdate();
  }

  _onModeChanged(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    const value = ev.detail?.value || ev.target.value;
    this._edited.runtime_mode = value;
    this._save();
    this.requestUpdate();
  }

  _onNumberChanged(key, ev) {
    const value = parseFloat(ev.target.value);
    if (!isNaN(value)) {
      this._edited[key] = value;
      this._editingFields.add(key);
      this._data[key] = value;
    } else {
      delete this._edited[key];
      this._editingFields.delete(key);
    }
  }

  async _onNumberBlur(key, ev) {
    this._editingFields.delete(key);
    if (this._edited[key] !== undefined) {
      await this._save();
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

  _findEntityId(domain, suffix) {
    const statusEntity = this.config.pid_entity;
    const deviceName = statusEntity.replace(/^sensor\./, "").replace(/_status$/, "");
    const candidateId = `${domain}.${deviceName}_${suffix}`;
    
    // Check if entity exists
    if (this.hass.states[candidateId]) {
      return candidateId;
    }
    
    // Try alternative: search for entity with matching suffix
    const prefix = `${domain}.${deviceName}`;
    for (const entityId in this.hass.states) {
      if (entityId.startsWith(prefix) && entityId.endsWith(`_${suffix}`)) {
        return entityId;
      }
    }
    
    // Fallback to candidate
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
      
      for (const [key, entitySuffix] of Object.entries(numberMappings)) {
        if (patch[key] !== undefined) {
          const entityId = this._findEntityId("number", entitySuffix);
          try {
            // Call the service - this should trigger the entity's async_set_native_value
            // which updates the coordinator's _manual_sp_value and triggers a refresh
            await this.hass.callService("number", "set_value", {
              entity_id: entityId,
              value: patch[key],
            });
            
            // Give the service call time to complete and trigger coordinator update
            // The entity's async_set_native_value is async, so we need to wait a bit
            await new Promise(resolve => setTimeout(resolve, 200));
            
            // Update _data immediately with saved value - this is the source of truth
            this._data[key] = patch[key];
            // Mark as saved with timestamp - this prevents overwriting for 10 seconds
            this._savedFields.set(key, now);
            // Remove from _edited since it's now saved
            delete this._edited[key];
            console.log(`Saved ${key} = ${patch[key]} to ${entityId}, marked as saved at ${now}, will protect for 10 seconds`);
            
            // If this is manual_sp, the effective_sp will update after coordinator refresh
            // The coordinator's async_set_manual_sp should have been called by the entity
            // and async_request_refresh should trigger a recalculation
            if (key === "manual_sp") {
              const expectedSP = patch[key];
              console.log(`Waiting for effective_sp to update to ${expectedSP}...`);
              
              // Update immediately to get current state
              this._updateReadOnlyValues();
              
              // Check if effective_sp has updated to match our saved manual_sp
              const checkSPUpdate = () => {
                const state = this.hass?.states[this.config?.pid_entity];
                if (!state?.attributes) return false;
                
                const currentSP = state.attributes.effective_sp;
                const currentManualSP = state.attributes.manual_sp;
                
                console.log(`Checking: effective_sp=${currentSP}, manual_sp=${currentManualSP}, expected=${expectedSP}`);
                
                if (currentSP !== null && currentSP !== undefined) {
                  const spDiff = Math.abs(currentSP - expectedSP);
                  if (spDiff < 0.1) {
                    console.log(`✓ effective_sp updated to ${currentSP} (expected ${expectedSP})`);
                    this._updateReadOnlyValues();
                    return true; // Found the update
                  }
                }
                return false; // Not updated yet
              };
              
              // Check immediately first
              if (checkSPUpdate()) {
                console.log(`effective_sp already updated!`);
                return; // Already updated, no need to keep checking
              }
              
              // Check at intervals
              let checkCount = 0;
              const maxChecks = 20; // Check for up to 20 seconds (coordinator might have slow update interval)
              const checkInterval = setInterval(() => {
                checkCount++;
                this._updateReadOnlyValues();
                if (checkSPUpdate() || checkCount >= maxChecks) {
                  clearInterval(checkInterval);
                  if (checkCount >= maxChecks) {
                    console.warn(`effective_sp did not update to ${expectedSP} after ${maxChecks} checks. Coordinator may not be refreshing.`);
                  }
                }
              }, 1000); // Check every second
            }
          } catch (err) {
            console.error(`Error saving ${key} to ${entityId}:`, err);
            alert(`Error saving ${key}: ${err.message || err}`);
            throw err;
          }
        }
      }
      
      this._edited = {};
      this.requestUpdate();
    } catch (err) {
      console.error("Error saving PID settings:", err);
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
    if (this.hass?.callService) {
      try {
        this.hass.callService("browser_mod", "close_popup", {});
      } catch (e) {
        // Ignore
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

