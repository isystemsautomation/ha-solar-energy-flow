# Solar Energy Flow Controller

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/isystemsautomation/ha-solar-energy-flow?display_name=tag)](https://github.com/isystemsautomation/ha-solar-energy-flow/releases)
[![License](https://img.shields.io/github/license/isystemsautomation/ha-solar-energy-flow)](LICENSE)
[![Issues](https://img.shields.io/github/issues/isystemsautomation/ha-solar-energy-flow)](https://github.com/isystemsautomation/ha-solar-energy-flow/issues)

A **PID-based control integration for Home Assistant** that regulates a numeric output entity based on a measured process value and a setpoint, with optional grid import/export limiting.

Designed for **energy flow control** scenarios such as inverter power limiting, load control, or grid balancing.

---

## Features

- PID controller (Kp / Ki / Kd)
- Anti-windup with tracking
- Derivative on measurement
- Multiple runtime modes:
  - Automatic setpoint
  - Manual setpoint
  - Manual output
  - Hold
- Optional grid import/export limiter
- Optional output rate limiting
- Fully configurable from the Home Assistant UI
- Uses `DataUpdateCoordinator`

---

## Installation (HACS)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add this repository URL and select **Integration**
3. Install **Solar Energy Flow Controller**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration**
6. Search for **Solar Energy Flow Controller**

---

## Initial Configuration

During setup you must select:

| Item | Description | Supported Domains |
|---|---|---|
| Process Value (PV) | Measured value for control | `sensor`, `number`, `input_number` |
| Setpoint (SP) | Target value | `number`, `input_number` |
| Output | Controlled output | `number`, `input_number` |
| Grid Power | Grid power measurement | `sensor`, `number`, `input_number` |

Invalid entity domains are rejected during setup.

### Wiring Options (Configure dialog)

After installation you can adjust how signals are interpreted:

- **Invert PV** – flips the sign of the process value (PV) if your meter reports the opposite direction.
- **Invert SP** – flips the setpoint if a negative target is required.
- **Invert Grid Power** – flips the sign of the grid power measurement to match your hardware’s convention.
- **PID mode (direct / reverse)** – choose controller action so that positive error drives the output in the correct direction for your device.

---

## Runtime Modes

Selectable via a **Select** entity.

| Mode | Description |
|---|---|
| **AUTO SP** | PID controls output using external setpoint |
| **MANUAL SP** | User sets setpoint manually, PID remains active |
| **MANUAL OUT** | User directly controls output |
| **HOLD** | Output frozen at last value |

Mode changes attempt to avoid output jumps using bumpless transfer.

---

## Grid Limiter

Optional limiter that modifies the effective PID setpoint based on grid power.

### Limiter Types
- **Import** – limits grid import above a threshold
- **Export** – limits grid export beyond a threshold

### Characteristics
- Uses hysteresis (deadband)
- Alters PID inputs, not the PID algorithm itself
- Limiter state is exposed as a diagnostic sensor

---

## Rate Limiter

When enabled:
- Limits output change per second
- Applied after PID saturation
- Prevents rapid output swings

Configured via:
- Rate limiter enabled (switch)
- Rate limit (number, units: points/s)

---

## Entities Created

### Sensors
- Effective SP
- PV value
- Output
- Output (pre rate limit)
- Error
- Grid power
- P / I / D terms
- Limiter state (diagnostic)
- Status

### Number Entities

**Configuration**
- Kp, Ki, Kd
- Min output
- Max output
- PID deadband
- Grid limiter limit
- Grid limiter deadband
- Rate limit

**Runtime**
- Manual SP
- Manual OUT

Manual numbers are only writable when the corresponding runtime mode is active.  
Otherwise, edits are rejected and values snap back.

### Select Entities
- Runtime mode
- Grid limiter type (import / export)

### Switch Entities
- Enabled
- Grid limiter enabled
- Rate limiter enabled

---

## Status Sensor Values

The `Status` sensor may report:

- `running`
- `disabled`
- `hold`
- `manual_out`
- `missing_input`
- `invalid_output`
- `grid_power_unavailable`
- `limiting_import`
- `limiting_export`
- `output_write_failed`

These reflect internal controller and error states.

---

## Update Interval

- Configurable in seconds
- Minimum: 1 second
- Default: 10 seconds
- Applied dynamically without restart

---

## Limitations

- Output entity **must** be `number` or `input_number`
- Designed for slow energy systems, not real-time control
- No YAML configuration
- Safety limits rely on correct configuration of min/max output

---

## Support

- Issues: https://github.com/isystemsautomation/ha-solar-energy-flow/issues
- Documentation: https://github.com/isystemsautomation/ha-solar-energy-flow/

---

## License

MIT
