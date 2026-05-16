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

## Removing ghost devices

SkylinkNet can report old or invalid device IDs through the cloud socket. Because battery-powered sensors may only report occasionally, the integration remembers seen device IDs so they survive restarts. If a ghost device is remembered, Home Assistant may only let you disable it in the UI.

After updating to version `0.1.2` or newer and restarting Home Assistant, remove ghost entries from the device page, not the entity page. Home Assistant only enables deletion for devices when an integration explicitly supports device removal.

Use the `skylinknet.forget_device` service to remove one:

```yaml
action: skylinknet.forget_device
data:
  skylinknet_device_id: "ABCDEF12"
  ignore_future_events: true
```

The raw ID is shown in each entity's `device_id` attribute. Keeping `ignore_future_events` set to `true` prevents the ghost from being recreated if the SkylinkNet cloud reports it again.

If you later want that ID to be discoverable again, call:

```yaml
action: skylinknet.allow_device
data:
  skylinknet_device_id: "ABCDEF12"
```

## Limitations

This depends on Skylink's undocumented cloud WebSocket and may break if Skylink changes the app protocol.
