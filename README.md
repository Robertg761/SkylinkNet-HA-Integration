# SkylinkNet Home Assistant Integration

Unofficial Home Assistant custom integration for SkylinkNet hubs using the cloud WebSocket observed from the Android app.

## Status

This is an undocumented cloud integration. It does not use RTL-SDR, IFTTT, or a local hub API.

Confirmed behavior:

- Connects to `wss://api-1.skyhm.net/websock/hu/<hub_id>/<hub_key>`.
- Receives push `op=report` sensor events.
- Motion sensor `status=1` means active and `status=0` means normal.
- Works even when the mobile app is stopped.

Not implemented yet:

- Alarm arm/disarm commands.
- Device metadata loading through authenticated HTTP.
- Local hub control.

## Install

### HACS custom repository

1. In Home Assistant, open HACS.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/Robertg761/SkylinkNet-HA-Integration` as an **Integration** repository.
4. Install **SkylinkNet** from HACS.
5. Restart Home Assistant.

### Manual install

Copy `custom_components/skylinknet` into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Configure

Add the integration from Home Assistant:

Settings -> Devices & services -> Add integration -> SkylinkNet

You need:

- Hub ID
- Hub key

The hub key is sensitive. Treat it like a password.

## Entities

The integration creates binary sensors dynamically when the hub sends events. Unknown devices are named from their device ID until you rename them in Home Assistant.

By default, new devices use the `motion` binary sensor device class because this integration was first verified with a motion sensor. You can change the default device class in the integration options.

## Limitations

This depends on Skylink's undocumented cloud WebSocket and may break if Skylink changes the app protocol.
