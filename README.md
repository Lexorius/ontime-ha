# Ontime Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Lexorius/ontime-ha.svg)](https://github.com/Lexorius/ontime-ha/releases)
[![GitHub Activity](https://img.shields.io/github/commit-activity/y/Lexorius/ontime-ha.svg)](https://github.com/Lexorius/ontime-ha/commits/main)
[![License](https://img.shields.io/github/license/Lexorius/ontime-ha.svg)](LICENSE)

This Home Assistant integration allows you to control and monitor [Ontime](https://www.getontime.no/) - a professional show control timer application. Perfect for theaters, events, broadcasts, and any situation requiring precise time management.

## ✨ Features

### 📊 Real-time Monitoring
- **Timer Status**: Current timer value (including negative/overtime values)
- **Playback State**: Play, pause, or stop status
- **Current Event**: Active event information with all metadata
- **Overtime Detection**: Automatic detection when timers go negative
- **Elapsed Time**: Track how much time has passed
- **Expected End Time**: Know when the current event should finish

### 🎮 Full Control
- Start, pause, and stop timers
- Load and start specific events
- Navigate through your rundown (by ID, index, or cue)
- Add or subtract time on the fly
- Roll to the next event
- Reload the entire rundown

### 🔔 Smart Automations
- **Overtime Events**: Automatically fires when a timer goes negative
- Create complex automations based on timer states
- Trigger actions at specific time thresholds
- React to playback state changes

## 📋 Prerequisites

- Home Assistant 2023.1.0 or newer
- Ontime server running and accessible via network
- Ontime API v1 (Ontime version 2.0.0+)

## 🚀 Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu in the top right
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/Lexorius/ontime-ha`
6. Select category: "Integration"
7. Click "Add"
8. Find "Ontime" in the integrations list and click "Install"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/Lexorius/ontime-ha/releases)
2. Extract the `ontime` folder to your `custom_components` directory:
   ```
   config/
   └── custom_components/
       └── ontime/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── const.py
           ├── sensor.py
           ├── services.yaml
           └── translations/
               └── en.json
   ```
3. Restart Home Assistant

## ⚙️ Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Ontime"
4. Enter your Ontime server details:
   - **Host**: IP address or hostname of your Ontime server
   - **Port**: API port (default: 4001)
5. Click **Submit**

## 📊 Available Sensors

| Sensor | Entity ID | Description |
|--------|-----------|-------------|
| Timer | `sensor.ontime_timer` | Current timer value in milliseconds (can be negative) |
| Playback State | `sensor.ontime_playback_state` | Current playback status (play/pause/stop) |
| Current Event | `sensor.ontime_current_event` | Name and details of the active event |
| Overtime | `sensor.ontime_overtime` | Seconds of overtime (when timer is negative) |
| Elapsed Time | `sensor.ontime_elapsed` | Elapsed time in milliseconds |
| Expected End | `sensor.ontime_expected_end` | Timestamp when current event should end |

## 🛠️ Available Services

### Playback Control

| Service | Description | Parameters |
|---------|-------------|------------|
| `ontime.start` | Start the timer | None |
| `ontime.pause` | Pause the timer | None |
| `ontime.stop` | Stop the timer | None |
| `ontime.reload` | Reload the rundown | None |
| `ontime.roll` | Roll to next event | None |

### Event Control

| Service | Description | Parameters |
|---------|-------------|------------|
| `ontime.load_event` | Load an event by ID | `event_id` (string) |
| `ontime.start_event` | Load and start an event | `event_id` (string) |
| `ontime.load_event_index` | Load event by index | `event_index` (number) |
| `ontime.load_event_cue` | Load event by cue | `event_cue` (string) |

### Time Manipulation

| Service | Description | Parameters |
|---------|-------------|------------|
| `ontime.add_time` | Add/subtract time | `time` (ms), `direction` (both/start/duration/end) |

## 🎯 Events

### `ontime_overtime_started`

Fired when a timer goes into overtime (negative values).

**Event Data:**
- `entity_id`: The overtime sensor entity
- `event_title`: Name of the current event
- `overtime_seconds`: Number of seconds overtime

## 🤖 Automation Examples

### Alert on Overtime

```yaml
automation:
  - alias: "Alert when timer goes overtime"
    trigger:
      - platform: event
        event_type: ontime_overtime_started
    action:
      - service: notify.mobile_app_phone
        data:
          title: "⏰ Timer Overtime!"
          message: "{{ trigger.event.data.event_title }} is {{ trigger.event.data.overtime_seconds }}s over!"
          data:
            color: "red"
            importance: "high"
```

### Warning Light at 30 Seconds

```yaml
automation:
  - alias: "Warning at 30 seconds remaining"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ontime_timer
        below: 30000
        above: 0
    action:
      - service: light.turn_on
        target:
          entity_id: light.stage_warning
        data:
          color_name: yellow
          brightness: 255
          flash: long
```

### Auto-start Next Event

```yaml
automation:
  - alias: "Auto-roll on completion"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ontime_timer
        below: 0
        for:
          seconds: 5
    condition:
      - condition: state
        entity_id: sensor.ontime_playback_state
        state: "play"
    action:
      - service: ontime.roll
      - service: ontime.start
```

### Status Dashboard Light

```yaml
automation:
  - alias: "Update status light based on playback"
    trigger:
      - platform: state
        entity_id: sensor.ontime_playback_state
    action:
      - choose:
          - conditions:
              - condition: state
                entity_id: sensor.ontime_playback_state
                state: "play"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.status_indicator
                data:
                  color_name: green
          - conditions:
              - condition: state
                entity_id: sensor.ontime_playback_state
                state: "pause"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.status_indicator
                data:
                  color_name: yellow
          - conditions:
              - condition: state
                entity_id: sensor.ontime_playback_state
                state: "stop"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.status_indicator
                data:
                  color_name: red
```

## 📱 Lovelace Card Example

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Ontime Control
    entities:
      - entity: sensor.ontime_playback_state
        name: Status
      - entity: sensor.ontime_current_event
        name: Current Event
      - entity: sensor.ontime_timer
        name: Timer
      - entity: sensor.ontime_overtime
        name: Overtime

  - type: horizontal-stack
    cards:
      - type: button
        tap_action:
          action: call-service
          service: ontime.start
        icon: mdi:play
        name: Start
        
      - type: button
        tap_action:
          action: call-service
          service: ontime.pause
        icon: mdi:pause
        name: Pause
        
      - type: button
        tap_action:
          action: call-service
          service: ontime.stop
        icon: mdi:stop
        name: Stop
        
      - type: button
        tap_action:
          action: call-service
          service: ontime.roll
        icon: mdi:skip-next
        name: Next

  - type: gauge
    entity: sensor.ontime_timer
    name: Time Remaining
    unit: s
    min: -300
    max: 3600
    severity:
      green: 60
      yellow: 30
      red: 0
```

## 🐛 Troubleshooting

### Integration won't connect
1. Verify Ontime is running and accessible
2. Check the API is enabled in Ontime settings
3. Test the connection: `http://[YOUR_IP]:4001/api/v1/info`
4. Check Home Assistant logs: **Settings** → **System** → **Logs**

### Sensors show "Unavailable"
1. Check network connectivity
2. Restart the Ontime server
3. Reload the integration in Home Assistant
4. Check if Ontime API version is compatible (v1)

### Overtime events not firing
1. Ensure the overtime sensor is enabled
2. Check that your automation is correctly configured
3. Verify the timer actually goes negative (some Ontime configs stop at 0)

## 🔧 Development

### Local Testing
```bash
# Clone the repository
git clone https://github.com/Lexorius/ontime-ha.git

# Create symbolic link for development
ln -s /path/to/ontime-ha/custom_components/ontime /path/to/ha/config/custom_components/ontime

# Restart Home Assistant
```

### Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.ontime: debug
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- [Ontime](https://www.getontime.no/)  the amazing timer software
- Home Assistant community for the great platform
- HACS for simplified distribution

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Lexorius/ontime-ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Lexorius/ontime-ha/discussions)

---

⭐ If you find this integration useful, please star the repository!
