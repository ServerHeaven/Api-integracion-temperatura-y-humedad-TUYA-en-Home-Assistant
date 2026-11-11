#!/usr/bin/env python3
"""Lee temperatura, humedad y bateria de un sensor Tuya via Tuya Cloud OpenAPI.
Reads temperature, humidity and battery of a Tuya sensor via the Tuya Cloud OpenAPI.

Solo libreria estandar / Standard library only (funciona en el contenedor de HA).

Uso / Usage:
  python3 tuya_th.py              -> JSON para Home Assistant / JSON for Home Assistant
  python3 tuya_th.py --discover   -> status + specifications crudos / raw status + specs

Configuracion / Config: /config/tuya_api.json (ver / see tuya_api.example.json)
NO versionar ese fichero / DO NOT commit that file.

NOTA / NOTE: firma y endpoints segun la documentacion de Tuya OpenAPI (HMAC-SHA256
v2). Revisar con --discover contra tu cuenta antes de fiarte de los valores.
"""
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request

CONFIG = os.environ.get("TUYA_CONFIG", "/config/tuya_api.json")
TOKEN_CACHE = os.environ.get("TUYA_TOKEN_CACHE", "/config/.tuya_token.json")

# Centro de datos -> endpoint. Debe coincidir con el de tu proyecto cloud.
# Data center -> endpoint. Must match your cloud project's data center.
ENDPOINTS = {
    "eu": "https://openapi.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}

# Codigos DP habituales (varian por modelo/categoria; comprobar con --discover).
# Common DP codes (vary by model/category; check with --discover).
TEMP_CODES = ["va_temperature", "temp_current"]
HUM_CODES = ["va_humidity", "humidity_value"]
BAT_CODES = ["battery_percentage", "battery_state"]


def load_config():
    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for key in ("client_id", "client_secret", "device_id"):
        if not cfg.get(key):
            raise RuntimeError(f"Falta/missing '{key}' en/in {CONFIG}")
    if not cfg.get("endpoint"):
        region = cfg.get("region", "eu")
        if region not in ENDPOINTS:
            raise RuntimeError(f"region '{region}' desconocida/unknown; usa/use 'endpoint'")
        cfg["endpoint"] = ENDPOINTS[region]
    return cfg


def api(cfg, path, token=None):
    """GET firmado / signed GET (Tuya HMAC-SHA256)."""
    t = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    content_sha = hashlib.sha256(b"").hexdigest()  # GET sin cuerpo / no body
    string_to_sign = "\n".join(["GET", content_sha, "", path])
    message = cfg["client_id"] + (token or "") + t + nonce + string_to_sign
    sign = hmac.new(
        cfg["client_secret"].encode(), message.encode(), hashlib.sha256
    ).hexdigest().upper()
    headers = {
        "client_id": cfg["client_id"],
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "sign_method": "HMAC-SHA256",
    }
    if token:
        headers["access_token"] = token
    req = urllib.request.Request(cfg["endpoint"] + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Red/network error: {exc}") from exc
    if not data.get("success"):
        # p.ej. 1004 sign invalid, 28841002 suscripcion caducada / subscription expired
        raise RuntimeError(f"Tuya API error {data.get('code')}: {data.get('msg')}")
    return data["result"]


def get_token(cfg):
    """Token con cache: no pedir uno nuevo en cada sondeo / cached token."""
    try:
        with open(TOKEN_CACHE, encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached.get("expires_at", 0) > time.time() + 60 and cached.get("client_id") == cfg["client_id"]:
            return cached["access_token"]
    except (OSError, ValueError):
        pass
    result = api(cfg, "/v1.0/token?grant_type=1")
    cached = {
        "access_token": result["access_token"],
        "expires_at": time.time() + int(result.get("expire_time", 7200)),
        "client_id": cfg["client_id"],
    }
    try:
        with open(TOKEN_CACHE, "w", encoding="utf-8") as fh:
            json.dump(cached, fh)
        os.chmod(TOKEN_CACHE, 0o600)
    except OSError:
        pass
    return cached["access_token"]


def pick(status, codes):
    for code in codes:
        if code in status:
            return code, status[code]
    return None, None


def main():
    cfg = load_config()
    token = get_token(cfg)
    dev = cfg["device_id"]
    raw = api(cfg, f"/v1.0/devices/{dev}/status", token)  # lista de {code, value}
    status = {item["code"]: item["value"] for item in raw}

    if "--discover" in sys.argv:
        specs = api(cfg, f"/v1.0/devices/{dev}/specifications", token)
        print(json.dumps({"status": raw, "specifications": specs}, indent=2, ensure_ascii=False))
        return

    t_code, t_raw = pick(status, [cfg["temperature_code"]] if cfg.get("temperature_code") else TEMP_CODES)
    h_code, h_raw = pick(status, [cfg["humidity_code"]] if cfg.get("humidity_code") else HUM_CODES)
    b_code, b_raw = pick(status, [cfg["battery_code"]] if cfg.get("battery_code") else BAT_CODES)
    if t_raw is None:
        raise RuntimeError(
            "No hay codigo de temperatura / no temperature code. Codigos recibidos / got: "
            + ", ".join(status) + " (ejecuta/run --discover; si esta vacio, el dispositivo no expone DPs)"
        )

    # La temperatura suele venir x10 (235 -> 23.5). Ajustable por config.
    # Temperature usually arrives x10 (235 -> 23.5). Adjustable in config.
    t_div = float(cfg.get("temperature_divisor", 10))
    h_div = float(cfg.get("humidity_divisor", 1))
    out = {
        "temperature": round(t_raw / t_div, 1),
        "humidity": round(h_raw / h_div, 1) if h_raw is not None else None,
        "battery": b_raw,
        "codes": {"temperature": t_code, "humidity": h_code, "battery": b_code},
    }
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        sys.exit(1)
