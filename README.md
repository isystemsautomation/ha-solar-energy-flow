# Solar Energy Controller

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/isystemsautomation/ha-solar-energy-controller?display_name=tag)](https://github.com/isystemsautomation/ha-solar-energy-controller/releases)
[![Issues](https://img.shields.io/github/issues/isystemsautomation/ha-solar-energy-controller)](https://github.com/isystemsautomation/ha-solar-energy-controller/issues)

A **PID-based control integration for Home Assistant** that regulates a numeric output entity based on a measured process value and a setpoint, with optional grid import/export limiting.

Designed for **energy flow control** scenarios such as inverter power limiting, load control, EV charging, or grid balancing.

---

## About

Solar Energy Controller is an open-source PID control integration for Home Assistant, designed to provide flexible energy flow control for solar and grid-connected systems. This integration enables precise control of energy systems through a normalized, percent-based PID algorithm that works across different sensor types and units.

The integration is developed and maintained as an open-source project. For more information, visit the [GitHub repository](https://github.com/isystemsautomation/ha-solar-energy-controller/).

---

## Features

- PID controller (Kp / Ki / Kd)
- **Internal 0–100% normalized control**
- **Percent-based PID tuning** (unit- and device-independent)
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

---

## How the Controller Works

The controller internally **normalizes PV, SP, and Grid Power to a 0–100% range** using configured raw min/max values:

- **PV (Process Value)** → 0–100%
- **SP (Setpoint)** → 0–100%
- **GRID (Grid Power)** → 0–100% (used only when limiter is enabled)
- **PID OUT** → 0–100%

The PID algorithm **always operates in percent**, while:
- Sensors continue to display **raw, real-world values**
- The output entity receives **scaled real-world values** (based on your output min/max)

This makes the controller:
- stable across different sensors and units (W, A, V, %, etc.)
- predictable to tune
- resilient when changing devices (only ranges change)

---

## PID Gains (Percent-Based Tuning)

**Kp, Ki, and Kd are tuned in percent space.**

What this means:
- **100% PID output** represents your configured *maximum output*
- PV/SP/Grid units do not matter (because values are normalized before PID)
- Gains do **not** need re-scaling when you change sensor ranges or units

---

## Installation

### Prerequisites

- Home Assistant 2023.9.0 or later
- [HACS](https://hacs.xyz/) (Home Assistant Community Store) installed and configured

If you don't have HACS installed yet:
1. Follow the [HACS installation guide](https://hacs.xyz/docs/setup/download)
2. Restart Home Assistant
3. Complete the HACS setup wizard

### Installation Steps

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add this repository URL: `https://github.com/isystemsautomation/ha-solar-energy-controller` and select **Integration** as the category
3. Click **Add** and wait for the repository to be added
4. Search for **Solar Energy Controller** in HACS
5. Click **Download** to install the integration
6. Restart Home Assistant
7. Go to **Settings → Devices & Services → Add Integration**
8. Search for **Solar Energy Controller** and follow the setup wizard

---

## Removal

To remove the Solar Energy Controller integration:

1. Go to **Settings → Devices & Services**
2. Find **Solar Energy Controller** in the list of integrations
3. Click on the integration entry
4. Click the **⋮** (three dots) menu in the top right corner
5. Select **Delete** and confirm the removal
6. (Optional) To remove the integration files from HACS:
   - Go to **HACS → Integrations**
   - Find **Solar Energy Controller**
   - Click **⋮** → **Remove**
7. Restart Home Assistant to complete the removal

> **Note:** Removing the integration will delete all configuration entries and entities. Any automations or scripts that reference these entities will need to be updated.

---

## Initial Configuration

During setup you select the entities used by the controller and define their operating ranges for normalization.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration1.png" width="300">
</p>

### Installation Parameters

The following parameters are required during the initial setup:

**Name:**
- Description: A friendly name for this controller instance (e.g., "Solar Inverter Controller", "EV Charger PID").
- Where to find: Choose any descriptive name that helps you identify this controller in Home Assistant.

**Process Value Entity (PV):**
- Description: The entity that provides the measured process value that the PID controller will regulate. This is the "sensor" that tells you the current state.
- Where to find: Go to **Settings → Devices & Services → Entities** and search for your sensor. Examples: `sensor.solar_power`, `sensor.grid_voltage`, `number.current_setpoint`.
- Supported domains: `sensor`, `number`, `input_number`
- Example: If controlling solar inverter power, this would be your power sensor (e.g., `sensor.solar_inverter_power`).

**Setpoint Entity (SP):**
- Description: The entity that provides the target setpoint value. The PID controller will try to keep the process value equal to this setpoint.
- Where to find: Go to **Settings → Devices & Services → Entities** and search for your setpoint entity. This is typically a `number` or `input_number` entity that you can set manually or via automation.
- Supported domains: `number`, `input_number`
- Example: If you want to maintain 5000W, create an `input_number` entity (e.g., `input_number.target_power`) and set it to 5000.

**Output Entity:**
- Description: The entity that the PID controller will write to. This is the "actuator" that controls your system (e.g., inverter power limit, charger current).
- Where to find: Go to **Settings → Devices & Services → Entities** and search for your output entity. This must be a `number` or `input_number` entity that accepts numeric values.
- Supported domains: `number`, `input_number`
- Example: If controlling an inverter, this would be the power limit entity (e.g., `number.inverter_max_power`).

**Grid Power Entity:**
- Description: The entity that provides grid power measurement (signed import/export). Required if you plan to use the grid limiter feature.
- Where to find: Go to **Settings → Devices & Services → Entities** and search for your grid power sensor. This should be a sensor that reports positive values when importing from grid and negative when exporting.
- Supported domains: `sensor`, `number`, `input_number`
- Example: `sensor.grid_power` where positive = importing, negative = exporting.

**PV min / max:**
- Description: The minimum and maximum expected values for the process value in raw units. These define the range used to normalize the PV to 0–100% internally.
- Where to find: Check your process value sensor's typical operating range. For example, if your power sensor reads 0–10000W, set min=0, max=10000.
- Default: -5000.0 to 5000.0
- Example: If your PV sensor measures power in watts and ranges from 0W to 10000W, set PV min=0, PV max=10000.

**SP min / max:**
- Description: The minimum and maximum expected values for the setpoint in raw units. These define the range used to normalize the SP to 0–100% internally.
- Where to find: Check what range your setpoint entity accepts. This should match the range you want to control.
- Default: -5000.0 to 5000.0
- Example: If your setpoint can be set from 0W to 10000W, set SP min=0, SP max=10000.

**Grid min / max:**
- Description: The minimum and maximum expected values for grid power in raw units. These define the range used to normalize grid power to 0–100% internally (used by the grid limiter).
- Where to find: Check your grid power sensor's typical operating range. For example, if your grid sensor reads -5000W (export) to +5000W (import), set min=-5000, max=5000.
- Default: -5000.0 to 5000.0
- Example: If your grid sensor measures from -10000W (export) to +10000W (import), set Grid min=-10000, Grid max=10000.

> **Note:** These min/max ranges are used only to scale signals internally to 0–100% for PID calculation. They do not limit the actual sensor values or output. Invalid entity domains are rejected during setup.

---

## Wiring & PID Direction

After installation, you can configure signal interpretation and controller behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration2.png" width="300">
</p>

### Options

- **Process Value Entity** – Entity providing the measured process value
  - Supported domains: `sensor`, `number`, `input_number`
- **Setpoint Entity** – Entity providing the target setpoint
  - Supported domains: `number`, `input_number`
- **Output Entity** – Entity to be controlled by the PID
  - Supported domains: `number`, `input_number`
- **Grid Power Entity** – Entity providing grid power measurement
  - Supported domains: `sensor`, `number`, `input_number`
- **Invert PV** – Flips the sign of the process value if your meter reports the opposite direction (default: disabled)
- **Invert SP** – Flips the setpoint sign (default: disabled)
- **Invert Grid Power** – Flips grid power sign to match hardware conventions (default: disabled)
- **PID mode**
  - **Direct** – Increasing error increases output (default)
  - **Reverse** – Increasing error decreases output
- **Update interval** – Control loop execution interval in seconds (default: 10, minimum: 1)
- **PV min/max** – Scaling range for process value normalization in raw units (default: -5000.0 to 5000.0)
- **SP min/max** – Scaling range for setpoint normalization in raw units (default: -5000.0 to 5000.0)
- **Grid min/max** – Scaling range for grid power normalization in raw units (default: -5000.0 to 5000.0)

---

## Runtime Controls

Runtime controls allow switching modes and manually overriding behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration3.png" width="200">
</p>

### Runtime Modes

| Mode | Description |
|---|---|
| **AUTO SP** | PID controls output using normalized percent PV/SP (default) |
| **MANUAL SP** | User sets setpoint manually (raw units), PID remains active |
| **MANUAL OUT** | User directly controls output (raw units) |
| **HOLD** | Output frozen at last value |

Mode transitions use **bumpless transfer** to avoid output jumps.

### Runtime Parameters

- **Enabled** – Master enable/disable switch for the controller (default: enabled)
- **Runtime mode** – Current operating mode (AUTO SP, MANUAL SP, MANUAL OUT, HOLD)
- **Manual SP value** – Manual setpoint value in raw units (only active in MANUAL SP mode)
- **Manual OUT value** – Manual output value in raw units (only active in MANUAL OUT mode)

---

## Live Sensors & PID Internals

The integration exposes detailed runtime sensors for transparency and tuning.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration4.png" width="200">
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

> Note: PV/SP/Output sensors show raw values. PID calculations are performed internally in percent.

---

## Configuration Parameters

All tuning and limiter parameters are available as number and switch entities.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration5.png" width="200">
</p>

### PID & Limits

- **Kp, Ki, Kd** – PID gains (percent-based tuning)
  - Kp: Proportional gain (default: 1.0)
  - Ki: Integral gain (default: 0.1)
  - Kd: Derivative gain (default: 0.0)
- **PID deadband** – Deadband in percent (default: 0.0)
  - Output changes only when error exceeds this threshold
- **Min output** – Minimum output value in raw units (default: 0.0)
- **Max output** – Maximum output value in raw units (default: 11000.0)

### Grid Limiter

- **Grid limiter enabled** – Enable/disable grid power limiting (default: disabled)
- **Grid limiter type** – Import or export limiting
  - Import: Limits when importing from grid
  - Export: Limits when exporting to grid
- **Grid limiter limit** – Limit threshold in raw units (default: 1000.0)
- **Grid limiter deadband** – Deadband in raw units (default: 50.0)
  - Hysteresis to prevent oscillation around the limit

### Rate Limiter

- **Rate limiter enabled** – Enable/disable output rate limiting (default: disabled)
- **Rate limit** – Maximum output change rate in raw units per second (default: 0.0)
  - Prevents sudden output changes

### Advanced Parameters

- **Max output step** – Maximum allowed output step change (default: 0.0, disabled)
  - Limits the maximum change per update cycle
- **Output epsilon** – Minimum output change threshold (default: 0.0, disabled)
  - Output only changes if the difference exceeds this value

---

## Diagnostic Information

Additional diagnostic entities help understand controller behavior.

<p align="center">
  <img src="https://raw.githubusercontent.com/isystemsautomation/ha-solar-energy-controller/main/images/Configuration6.png" width="200">
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

## Data Updates

The Solar Energy Controller integration uses a **polling-based data update mechanism**. The integration periodically reads the current state of the configured entities (Process Value, Setpoint, Grid Power, and Output) and recalculates the PID output.

### Update Mechanism

- **Polling-based**: The integration actively polls Home Assistant entity states at regular intervals
- **Default polling interval**: 10 seconds
- **Configurable**: The update interval can be adjusted in the integration options (minimum: 1 second)
- **Dynamic updates**: Changes to the update interval are applied immediately without requiring a restart

### How It Works

1. At each update cycle, the coordinator:
   - Reads the current state of the Process Value (PV) entity
   - Reads the current state of the Setpoint (SP) entity
   - Reads the current state of the Grid Power entity (if configured)
   - Reads the current state of the Output entity
   - Normalizes all values to 0–100% using the configured min/max ranges
   - Calculates the PID output based on the error (SP - PV)
   - Applies grid limiter and rate limiter constraints
   - Writes the new output value to the Output entity

2. The update interval determines how frequently this cycle repeats

### Limitations

- **Polling overhead**: More frequent updates (lower interval) increase Home Assistant state reads and writes
- **Entity availability**: If any required entity becomes unavailable, the controller will log the issue and continue with the last known values where appropriate
- **Not real-time**: Due to polling, there is a delay between actual changes in sensor values and controller response (up to the update interval)
- **Designed for slow systems**: The integration is optimized for energy systems with seconds-level dynamics, not millisecond-level real-time control

### Recommended Settings

- **Energy systems (solar, grid, EV charging)**: 10–30 seconds (default: 10 seconds)
- **Faster response needed**: 5–10 seconds (increases system load)
- **Very slow systems**: 30–60 seconds (reduces system load)

---

## Limitations

- Output entity **must** be `number` or `input_number`
- Designed for slow energy systems (seconds-level dynamics)
- Not intended for real-time control
- No YAML configuration

---

## Support

- Issues: https://github.com/isystemsautomation/ha-solar-energy-controller/issues
- Documentation: https://github.com/isystemsautomation/ha-solar-energy-controller/
