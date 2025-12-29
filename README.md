# Solar Energy Flow Controller

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/isystemsautomation/ha-solar-energy-flow?display_name=tag)](https://github.com/isystemsautomation/ha-solar-energy-flow/releases)
[![Issues](https://img.shields.io/github/issues/isystemsautomation/ha-solar-energy-flow)](https://github.com/isystemsautomation/ha-solar-energy-flow/issues)

A **PID-based control integration for Home Assistant** that regulates a numeric output entity based on a measured process value and a setpoint, with optional grid import/export limiting.

Designed for **energy flow control** scenarios such as inverter power limiting, load control, EV charging, or grid balancing.

---

## Features

- PID controller (Kp / Ki / Kd)
- **Internal 0–100% normalized control**
- Percent-based PID tuning (device-independent)
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

## How the Controller Works (Important)

Internally, the controller **normalizes all control signals to a 0–100% range**:

- Process Value (PV) → 0–100%
- Setpoint (SP) → 0–100%
- PID Output → 0–100%

This normalization is done using user-configured **minimum and maximum values** for each signal.

The PID algorithm **always operates in percent**, while:
- Sensors continue to display **raw, real-world values**
- The output entity receives **scaled real-world values**

This design provides:
- Stable tuning across different devices
- Predictable PID behavior
- Independence from sensor units (W, A, V, %, etc.)

---

## PID Gains (Percent-Based Tuning)

**Kp, Ki, and Kd are tuned in percent space.**

What this means:
- A PID output of **100%** represents the maximum configured output
- PID gains are **independent of the physical units** of PV, SP, or output
- Changing sensors or ranges does not require re-scaling PID gains

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

During setup you must select the entities used by the controller and define their operating ranges.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration1.png" width="300">
</p>

| Item | Description | Supported Domains |
|---|---|---|
| Process Value (PV) | Measured value for control | `sensor`, `number`, `input_number` |
| Setpoint (SP) | Target value | `number`, `input_number` |
| Output | Controlled output | `number`, `input_number` |
| Grid Power | Grid power measurement (optional) | `sensor`, `number`, `input_number` |

Invalid entity domains are rejected during setup.

---

## Wiring & PID Direction

After installation, you can configure signal interpretation and controller behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration2.png" width="300">
</p>

### Options
- **Invert PV** – flips the sign of the process value if your meter reports the opposite direction
- **Invert SP** – flips the setpoint sign
- **Invert Grid Power** – flips grid power sign to match hardware conventions
- **PID mode**
  - **Direct** – increasing error increases output
  - **Reverse** – increasing error decreases output
- **Update interval** – control loop execution interval (seconds)

---

## Runtime Controls

Runtime controls allow switching modes and manually overriding behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration3.png" width="200">
</p>

### Runtime Modes

| Mode | Description |
|---|---|
| **AUTO SP** | PID controls output using normalized percent setpoint |
| **MANUAL SP** | User sets setpoint manually (raw units), PID remains active |
| **MANUAL OUT** | User directly controls output (raw units) |
| **HOLD** | Output frozen at last value |

Mode transitions use **bumpless transfer** to avoid output jumps.

---

## Live Sensors & PID Internals

The integration exposes detailed runtime sensors for transparency and tuning.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration4.png" width="200">
</p>

### Sensors
- Effective SP (raw units)
- PV value (raw units)
- Output (raw units)
- Output (pre rate limit)
- Error (percent domain)
- Grid power (raw units)
- P / I / D terms (percent domain)
- Limiter state (diagnostic)
- Status

---

## Configuration Parameters

All tuning and limiter parameters are available as number and switch entities.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration5.png" width="200">
</p>

### PID & Limits
- Kp, Ki, Kd (**percent-based tuning**)
- PID deadband (percent)
- Min output (raw units)
- Max output (raw units)

### Grid Limiter
- Grid limiter enabled
- Grid limiter type (import / export)
- Grid limiter limit (raw units)
- Grid limiter deadband

### Rate Limiter
- Rate limiter enabled
- Rate limit (output units per second)

---

## Diagnostic Information

Additional diagnostic entities help understand controller behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-flow/main/images/Configuration6.png" width="200">
</p>

### Diagnostic Entities
- Limiter state
- Output (pre rate limit)

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

These reflect internal controller state and error conditions.

---

## Update Interval

- Configurable in seconds
- Minimum: 1 second
- Default: 10 seconds
- Applied dynamically without restart

---

## Limitations

- Output entity **must** be `number` or `input_number`
- Designed for slow energy systems (seconds-level dynamics)
- Not intended for real-time control
- No YAML configuration

---

## Support

- Issues: https://github.com/isystemsautomation/ha-solar-energy-flow/issues
- Documentation: https://github.com/isystemsautomation/ha-solar-energy-flow/
