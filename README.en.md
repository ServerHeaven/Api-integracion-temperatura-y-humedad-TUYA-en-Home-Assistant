# Tuya Temperature & Humidity Sensors in Home Assistant

🌐 [Español](README.md) · **English**

A guide to bringing Tuya / Smart Life temperature and humidity sensors into Home Assistant (HA), reviewed against the official documentation. It covers which method to pick, how to set up the **cloud API** for sensors the official integration does not recognise, and the usual failure modes.

> **Notice.** Integrating these sensors "only through the cloud API" (a Tuya developer project) is **no longer the recommended path** and has several traps (expiring trial subscription, ×10 scaling, region). This guide separates the methods and flags each trap.

## 1. Which method to choose

| Method | Use when | Developer account | Works offline | Notes |
|---|---|---|---|---|
| **A. Official Tuya integration** | First choice | No (QR login with the app) | No (cloud only) | *Cloud Push*. If the sensor exposes no data, nothing shows up |
| **B. Custom cloud API (script)** | Sensor is "unsupported" in A | **Yes** (project on iot.tuya.com) | No | Polling every X min. Covered by this guide |
| **C. [tuya-local](https://github.com/make-all/tuya-local)** | You want local and fast | No (app login to fetch the key) | Yes | **Battery-powered sensors without a hub cannot be supported locally** |
| **D. Zigbee (ZHA / Zigbee2MQTT)** | Zigbee sensors | No | Yes | Best option if you have not bought the sensor yet |

**Rule of thumb:** try A → if no entities appear, B (or C for mains-powered devices) → if you are still shopping, D.

## 2. Method A — Official integration (recommended first)

1. In the Tuya Smart / Smart Life app, add the device and note your **User Code** (*Me → gear icon → Account and Security*, at the bottom).
2. HA → *Settings → Devices & services → Add integration → Tuya*.
3. Scan the **QR code** shown by HA with the app.
4. When you add devices later: *Tuya → ⋮ → Reload*.

Per the [HA docs](https://www.home-assistant.io/integrations/tuya/), the integration talks only to the Tuya cloud and its IoT class is *Cloud Push*.

**If entities are missing:** download the device *diagnostics* and check the `status`, `status_range` and `function` keys. If all three are empty, the integration has nothing to read (it happens with some sensors that Tuya registers under another category; see §5). If HA keeps asking to re-authenticate, log in to iot.tuya.com and accept the terms and conditions, restart HA and reconfigure.

## 3. Method B — Cloud API with a script

Use it only if A does not expose the sensor **but the Tuya app does show the data**.

### 3.1 Tuya cloud project

1. Create an account at [iot.tuya.com](https://iot.tuya.com) and a *Cloud Project* (development method: *Smart Home*). **The data center must match your app account's region** (app: *Me → Settings → Account and Security → Region*).
2. In *Overview*, copy the **Access ID** and **Access Secret**.
3. *Devices → Link Tuya App Account → Add App Account* and scan the QR with the **same account** as the app.
4. *Cloud → API Services*: subscribe to and authorize the services Tuya requires for your project (in Tuya's guide, error `28841105` = project not authorized for that API). If the script returns permission errors, check here which service is missing.
5. Copy the **Device ID** (listed under *Devices → All Devices*).

### 3.2 Script and configuration

```text
/config/
├── scripts/tuya_th.py          ← from this repo: scripts/tuya_th.py
├── tuya_api.json               ← copy of scripts/tuya_api.example.json with YOUR data (do NOT commit)
└── configuration.yaml          ← add the block from examples/configuration.yaml
```

1. Copy `scripts/tuya_th.py` to `/config/scripts/` and `scripts/tuya_api.example.json` to `/config/tuya_api.json`; fill in `client_id` (Access ID), `client_secret` (Access Secret), `device_id` and `region` (`eu`, `us`, `cn`, `in`; or a full `endpoint`).
2. **Discover your sensor's real codes** (do not assume them):
   ```bash
   python3 /config/scripts/tuya_th.py --discover
   ```
   It prints `status` (codes and values) and `specifications` (ranges and scale). If `status` is empty, the sensor exposes no data through the API (see §5).
3. If your codes are not the usual ones, pin them in `tuya_api.json`: `temperature_code`, `humidity_code`, `battery_code`.
4. Adjust the scaling: temperature usually arrives **×10** (`235` = 23.5 °C), hence `temperature_divisor: 10`. Confirm with `--discover`.
5. Copy the block from `examples/configuration.yaml`, check the configuration and restart HA.

The script uses only the Python standard library (fits the HA container), **caches the token** in `/config/.tuya_token.json`, and exits with an error (the entity becomes `unknown`) when the API fails instead of inventing values. Polling is set to 900 s (15 min) to avoid exhausting free-plan quotas.

> ⚠️ **Not tested against a live account in this repository.** The HMAC-SHA256 signing and endpoints follow Tuya's public OpenAPI documentation and community scripts, but always validate with `--discover` before automating anything.

## 4. Method C — tuya-local (summary)

- Install via HACS and sign in with your app account: it retrieves `device_id` and `local_key` without a developer account. Re-pairing the device in the app **changes the local key**.
- Many devices accept **only one local connection**: close other integrations/apps connecting locally.
- **Battery-powered sensors without a hub** cannot be supported locally because of their power management; hub-connected ones may work using the hub's ID/IP/key plus the `node_id`.
- Check your model in the repository's `DEVICES.md`; regional variants or firmware updates can break support.

## 5. Known problems (what probably went wrong)

| Symptom | Cause | Fix |
|---|---|---|
| Everything worked, then devices vanish; error `28841002 … subscription … expired` | The trial *IoT Core* subscription **expires** | *Cloud → My Services → Extend Trial Period* (up to 6 months, answer in ~1 working day). **Tuya does not guarantee extensions stay available**; some users report a paid plan being demanded after expiry. Alternative: method A (QR) or C |
| Sensor "unsupported" / no entities in A | Registered under another category (e.g. `tdq`, a socket, instead of `wsdcg`, the T&H sensor) or empty `status_range`/`status` | Method B (if the API returns data) or C; or a quirk in core, which is out of your hands |
| Temperature 10× too high (235 °C) | Raw value with scale 1 (÷10) | `temperature_divisor: 10` and verify with `--discover` |
| `1004 sign invalid` | Wrong Access ID/Secret | Copy both again from *Overview* |
| `28841105` project not authorized for this API | API services not authorized in the project | Subscribe to and authorize the required services |
| No data / device not found | Project data center ≠ app account region, or app account not linked | Align the region (§3.1) and redo *Link Tuya App Account* |
| Endless re-authentication prompts (A) | Tuya terms and conditions changed | Accept terms at iot.tuya.com, restart HA, reconfigure |
| Bluetooth device "unavailable" (A) | The integration does not use HA's Bluetooth | Add it through a Tuya Bluetooth/multi-mode gateway |
| Stale values | Slow polling or a sleeping battery WiFi sensor | Normal for battery WiFi; do not set the interval below a few minutes |
| `Failed to retrieve device list` in tuya-local | Same expired-subscription problem when using cloud mode | Extend the trial or enter `device_id`/key manually |

**Note on Tuya's documentation:** Tuya's HA guide linked below describes the *old* flow (Access ID/Secret + Smart Life email/password, HA ≥ 2021.10.4). The official integration's current flow is the QR one; use that page only as a reference for error codes and trial extensions.

## 6. Security

- Never commit `tuya_api.json`, `.tuya_token.json` or `secrets.yaml` (already in `.gitignore`).
- Access Secret = your project's credential: regenerate it on iot.tuya.com if it leaks.
- With tuya-local, `local_key` is a credential: treat it the same way.

## 7. Repository contents

| Path | Description |
|---|---|
| `README.md` / `README.en.md` | This guide (ES / EN) |
| `scripts/tuya_th.py` | Minimal cloud API client (stdlib only), with `--discover` |
| `scripts/tuya_api.example.json` | Config template (no secrets) |
| `examples/configuration.yaml` | `command_line` + `template` sensors for HA |

## Sources

- [Tuya integration — Home Assistant](https://www.home-assistant.io/integrations/tuya/)
- [Tuya's guide for the HA integration (old flow, errors and trial extension)](https://developer.tuya.com/en/docs/iot/Home-assistant-tuya-intergration?id=Kb0eqjig0utdd)
- [tuya-local (make-all)](https://github.com/make-all/tuya-local)
- [HA forum: unsupported Tuya T&H sensor (`tdq` category, cloud script, ÷10)](https://community.home-assistant.io/t/tuya-t-h-sensor-unsupported/850996)
- [HA forum: options when Tuya IoT expires](https://community.home-assistant.io/t/other-options-when-tuya-iot-expired/542767)
- [HA forum: devices/entities gone missing (expired subscription)](https://community.home-assistant.io/t/tuya-devices-entities-gone-missing/347445?page=5)
- [tuya-home-assistant issue #804: IoT Core expired](https://github.com/tuya/tuya-home-assistant/issues/804)
