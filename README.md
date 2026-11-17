# Easee Local OCPP

Home Assistant becomes the **local OCPP 1.6J server** of your Easee chargers. Since firmware 344 Easee
chargers can talk OCPP to a server of your choice while the Easee cloud keeps working in parallel
(`DualProtocol`). This integration sets that up with a wizard and then gives you fast, local
measurements and control – without the cloud in the loop.

It is deliberately thin: it exposes what the charger offers via OCPP and leaves the logic (PV surplus
charging, schedules, notifications …) to automations or other integrations. It complements the
[Easee cloud integration](https://github.com/nordicopen/easee_hass); both can run side by side.

## Features
- **Setup wizard per charger**: checks firmware, Wi-Fi, operator and a dynamic circuit limit, suggests the
  address of Home Assistant, switches the charger to OCPP via the Easee cloud (generated basic-auth password)
  and waits until it connects. Roll back, reconfigure, and automatic switch back to cloud-only when you
  remove a charger.
- **No extra port**: the chargers connect to Home Assistant's own port
  (`ws://<home assistant>:8123/api/easee_ocpp/<serial>`), authenticated per charger.
- **Entities** (one device "<charger> OCPP" per charger): status, power, energy meter (energy dashboard),
  session energy and start, current and voltage per phase, offered current, effective charging limit,
  temperature, last RFID card, errors; connected / session / charging; max current; availability and
  remote start/stop; restart, reboot, unlock, refresh; plus one entity per OCPP configuration key of the
  charger (writable keys as switch/number/text, read-only keys as diagnostic sensors).
- **RFID with Home Assistant tags**: a card may charge if it is registered under *Settings → Tags*
  (tag ID = card ID). Accepted cards appear as tag scans (`tag_scanned`, last scanned), every decision
  fires `easee_ocpp_authorization`. Option: accept every card.
- **Actions** for controllers and power users: `easee_ocpp.set_current_limit` (expiring limit, see below),
  `get_configuration`, `change_configuration`, `set_charging_profile`, `clear_charging_profile`,
  `get_composite_schedule`, `trigger_message`, `send_local_list`, `get_local_list_version`. All accept a
  device or the charger serial.
- **Repairs** when a charger stays disconnected, keeps failing authentication or its address no longer
  points at Home Assistant; diagnostics with secrets redacted.

## Requirements
- Easee charger with firmware 344 or newer, on Wi-Fi, site operator "Easee", and you are owner/admin of the site.
- The charger must reach Home Assistant on port 8123 in your network. Use an IP address or a name your
  router resolves – chargers cannot resolve `.local` names.
- Home Assistant 2026.10 or newer.

## Installation
**HACS**: add this repository as custom repository (category *Integration*), install *Easee Local OCPP*,
restart Home Assistant.

**Manual**: download `easee_ocpp.zip` from the latest release and unpack it to
`config/custom_components/easee_ocpp/`, restart Home Assistant. (The repository itself does not contain
the generated Easee API client; the release package does.)

## Setup
1. *Settings → Devices & services → Add integration → Easee Local OCPP*, log in with your Easee account.
2. On the integration, *Add charger* and follow the wizard. It usually takes a few minutes until the
   charger connects.
3. Register your RFID cards as tags (*Settings → Tags*). Hold an unknown card to the charger: the sensor
   *Last RFID card* shows its ID.

> While OCPP is active the charger only charges after Home Assistant accepted the card.

## Expiring limits for controllers (e.g. PV surplus charging)
OCPP charging profiles are stacked: the integration keeps the **max current** number on stack level 0 and
`easee_ocpp.set_current_limit` sets a limit on stack level 1 that **expires** after `duration` seconds. A
controller renews the limit regularly; if the controller or Home Assistant stops, the charger falls back
to the max current. Set the max current to 0 A and charging stops when the controller is gone.

```yaml
action: easee_ocpp.set_current_limit
data:
  serial: EH123456
  current: 10        # A, 0 pauses charging
  duration: 120      # s, renew e.g. every 60 s
```

## Limitations
- Unencrypted `ws://` with basic auth (OCPP security profile 1): Easee only accepts TLS certificates from a
  public CA. Keep it inside your home network.
- Easee implements the OCPP profiles Core, SmartCharging, RemoteTrigger and LocalAuthListManagement – no
  firmware update, diagnostics upload or reservations via OCPP. Limits are in amperes.
- Equalizer setups are not covered; keep using the cloud integration for them.

## Development
- `python scripts/generate_easee_client.py` generates the Easee API client
  (`custom_components/easee_ocpp/easee_cloud_client`) from the pinned OpenAPI specification
  `openapi/easee-cloud-api.json` (`--download` refreshes it). The script keeps only the operations the
  integration uses and documents two corrections where the specification does not match the API.
- `python scripts/translations.py` writes `strings.json` and the English and German translations.
- Tests: `pip install -r requirements-dev.txt && pytest` (Linux; on Windows use `scripts/test-in-docker.sh`).
