# Sensores de temperatura y humedad Tuya en Home Assistant

🌐 **Español** · [English](README.en.md)

Guía para llevar sensores Tuya / Smart Life de temperatura y humedad a Home Assistant (HA), revisada contra la documentación oficial. Incluye qué método elegir, cómo montar la **API cloud** para los sensores que la integración oficial no reconoce, y los fallos típicos.

> **Aviso.** Integrar estos sensores "solo con la API cloud" (proyecto de desarrollador en Tuya) **ya no es el camino recomendado** y tiene varias trampas (suscripción de prueba que caduca, escalado ×10, región). Esta guía separa los métodos y marca cada trampa.

## 1. Qué método elegir

| Método | Cuándo usarlo | Requiere cuenta de desarrollador | Funciona sin internet | Notas |
|---|---|---|---|---|
| **A. Integración oficial Tuya** | Primera opción | No (login por QR con la app) | No (solo cloud) | Es *Cloud Push*. Si el sensor no expone datos, no aparecerá nada |
| **B. API cloud propia (script)** | El sensor sale "no compatible" en A | **Sí** (proyecto en iot.tuya.com) | No | Sondeo cada X min. Es lo que cubre esta guía |
| **C. [tuya-local](https://github.com/make-all/tuya-local)** | Quieres local y rapidez | No (login con la app para sacar la clave) | Sí | Los sensores **a pilas sin hub no se pueden soportar localmente** |
| **D. Zigbee (ZHA / Zigbee2MQTT)** | Sensores Zigbee | No | Sí | La mejor opción si aún no has comprado el sensor |

**Regla práctica:** prueba A → si no aparecen entidades, B (o C si es un sensor alimentado por red) → si vas a comprar, D.

## 2. Método A — Integración oficial (recomendado primero)

1. En la app Tuya Smart / Smart Life, añade el dispositivo y copia tu **User Code** (*Yo → engranaje → Cuenta y seguridad*, al final).
2. HA → *Ajustes → Dispositivos y servicios → Añadir integración → Tuya*.
3. Escanea con la app el **código QR** que muestra HA.
4. Si añades dispositivos después: *Tuya → ⋮ → Recargar*.

Según la [documentación de HA](https://www.home-assistant.io/integrations/tuya/), la integración habla solo con la nube Tuya y su clase IoT es *Cloud Push*.

**Si faltan entidades:** descarga los *diagnósticos* del dispositivo y mira las claves `status`, `status_range` y `function`. Si las tres están vacías, la integración no tiene nada que leer (sucede con algunos sensores que Tuya registra con otra categoría; ver §5). Si HA pide reautenticar repetidamente, entra en iot.tuya.com y acepta los términos y condiciones, reinicia HA y reconfigura.

## 3. Método B — API cloud con script

Úsalo solo si A no expone el sensor **pero la app Tuya sí muestra los datos**.

### 3.1 Proyecto cloud en Tuya

1. Crea cuenta en [iot.tuya.com](https://iot.tuya.com) y un *Cloud Project* (método de desarrollo: *Smart Home*). **El centro de datos debe corresponder a la región de tu cuenta de la app** (app: *Yo → Ajustes → Cuenta y seguridad → Región*).
2. En *Overview* copia **Access ID** y **Access Secret**.
3. *Devices → Link Tuya App Account → Add App Account* y escanea el QR con la **misma cuenta** de la app.
4. *Cloud → API Services*: suscribe y autoriza los servicios que pide Tuya para tu proyecto (en su guía, error `28841105` = proyecto sin autorizar para esa API). Si el script devuelve errores de permisos, revisa aquí qué servicio falta.
5. Copia el **Device ID** (listado en *Devices → All Devices*).

### 3.2 Script y configuración

```text
/config/
├── scripts/tuya_th.py          ← de este repo: scripts/tuya_th.py
├── tuya_api.json               ← copia de scripts/tuya_api.example.json con TUS datos (NO subir a git)
└── configuration.yaml          ← añade el bloque de examples/configuration.yaml
```

1. Copia `scripts/tuya_th.py` a `/config/scripts/` y `scripts/tuya_api.example.json` a `/config/tuya_api.json`; rellena `client_id` (Access ID), `client_secret` (Access Secret), `device_id` y `region` (`eu`, `us`, `cn`, `in`; o `endpoint` completo).
2. **Descubre los códigos reales de tu sensor** (no los supongas):
   ```bash
   python3 /config/scripts/tuya_th.py --discover
   ```
   Muestra `status` (códigos y valores) y `specifications` (rangos y escala). Si `status` sale vacío, el sensor no expone datos por la API (ver §5).
3. Si tus códigos no son los habituales, fíjalos en `tuya_api.json`: `temperature_code`, `humidity_code`, `battery_code`.
4. Ajusta el escalado: la temperatura suele llegar **×10** (`235` = 23,5 °C), de ahí `temperature_divisor: 10`. Compruébalo con `--discover`.
5. Copia el bloque de `examples/configuration.yaml`, comprueba la configuración y reinicia HA.

El script solo usa la librería estándar de Python (cabe en el contenedor de HA), **cachea el token** en `/config/.tuya_token.json` y sale con error (la entidad pasa a `unknown`) si la API falla, en lugar de inventar valores. El sondeo está a 900 s (15 min) para no agotar las cuotas del plan gratuito.

> ⚠️ **No probado contra una cuenta real en este repositorio.** La firma HMAC-SHA256 y los endpoints siguen la documentación pública de Tuya OpenAPI y los scripts de la comunidad, pero valida siempre con `--discover` antes de automatizar nada.

## 4. Método C — tuya-local (resumen)

- Instálalo por HACS y entra con tu cuenta de la app: recupera `device_id` y `local_key` sin cuenta de desarrollador. Reemparejar el dispositivo en la app **cambia la clave local**.
- Muchos dispositivos aceptan **una sola conexión local**: cierra otras integraciones/apps que se conecten en local.
- Los sensores **a pilas sin hub** no se pueden soportar localmente por su gestión de energía; los que van por hub pueden funcionar usando el ID/IP/clave del hub más el `node_id`.
- Comprueba tu modelo en `DEVICES.md` del repositorio; las variantes regionales o actualizaciones de firmware pueden romper el soporte.

## 5. Problemas conocidos (lo que probablemente falló)

| Síntoma | Causa | Solución |
|---|---|---|
| Todo funcionaba y de pronto no hay dispositivos; error `28841002 … subscription … expired` | La suscripción *IoT Core* de prueba **caduca** | *Cloud → My Services → Extend Trial Period* (hasta 6 meses, respuesta en ~1 día laborable). **Tuya no garantiza que las prórrogas sigan disponibles**; hay usuarios que reportan que tras caducar se exige un plan de pago. Alternativa: método A (QR) o C |
| Sensor "no compatible" / sin entidades en A | Registrado con otra categoría (p. ej. `tdq`, enchufe, en vez de `wsdcg`, sensor T&H) o `status_range`/`status` vacíos | Método B (si la API devuelve datos) o C; o un *quirk* en el núcleo, que no depende de ti |
| Temperatura 10× demasiado alta (235 °C) | Valor crudo con escala 1 (÷10) | `temperature_divisor: 10` y verificar con `--discover` |
| `1004 sign invalid` | Access ID/Secret incorrectos | Volver a copiar ambos desde *Overview* |
| `28841105` project not authorized for this API | Falta autorizar servicios API en el proyecto | Suscribir y autorizar los servicios requeridos |
| Sin datos / no encuentra el dispositivo | Centro de datos del proyecto ≠ región de la cuenta de la app, o cuenta de la app no enlazada | Alinear región (§3.1) y volver a *Link Tuya App Account* |
| Pide reautenticar una y otra vez (A) | Cambio de términos y condiciones de Tuya | Aceptar términos en iot.tuya.com, reiniciar HA, reconfigurar |
| Dispositivo Bluetooth "no disponible" (A) | La integración no usa el Bluetooth de HA | Añadirlo vía pasarela Tuya Bluetooth/multimodo |
| Valores obsoletos | Sondeo lento o sensor WiFi a pilas que duerme | Normal en WiFi a pilas; no bajes de varios minutos el intervalo |
| `Failed to retrieve device list` en tuya-local | Mismo problema de suscripción caducada al usar el modo cloud | Prórroga o introducir `device_id`/clave a mano |

**Nota sobre documentación de Tuya:** la guía de Tuya para HA enlazada abajo describe el flujo *antiguo* (Access ID/Secret + email/contraseña de Smart Life, HA ≥ 2021.10.4). El flujo actual de la integración oficial es el del QR; úsala solo como referencia para códigos de error y prórrogas.

## 6. Seguridad

- Nunca subas `tuya_api.json`, `.tuya_token.json` ni `secrets.yaml` (ya están en `.gitignore`).
- Access Secret = credencial de tu proyecto: si se filtra, regénerala en iot.tuya.com.
- Para tuya-local, `local_key` es una credencial: trátala igual.

## 7. Contenido del repositorio

| Ruta | Descripción |
|---|---|
| `README.md` / `README.en.md` | Esta guía (ES / EN) |
| `scripts/tuya_th.py` | Cliente mínimo de la API cloud (solo stdlib), con `--discover` |
| `scripts/tuya_api.example.json` | Plantilla de configuración (sin secretos) |
| `examples/configuration.yaml` | Sensores `command_line` + `template` para HA |

## Fuentes

- [Integración Tuya — Home Assistant](https://www.home-assistant.io/integrations/tuya/)
- [Guía de Tuya para la integración con HA (flujo antiguo, errores y prórroga)](https://developer.tuya.com/en/docs/iot/Home-assistant-tuya-intergration?id=Kb0eqjig0utdd)
- [tuya-local (make-all)](https://github.com/make-all/tuya-local)
- [Foro HA: sensor T&H Tuya no compatible (categoría `tdq`, script cloud, ÷10)](https://community.home-assistant.io/t/tuya-t-h-sensor-unsupported/850996)
- [Foro HA: opciones cuando caduca Tuya IoT](https://community.home-assistant.io/t/other-options-when-tuya-iot-expired/542767)
- [Foro HA: dispositivos/entidades desaparecidos (suscripción caducada)](https://community.home-assistant.io/t/tuya-devices-entities-gone-missing/347445?page=5)
- [Issue tuya-home-assistant #804: IoT Core expirado](https://github.com/tuya/tuya-home-assistant/issues/804)
