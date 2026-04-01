"""
licencia_online.py — Verificación de licencia via GitHub (modo híbrido offline-first)
"""

import urllib.request
import urllib.error
import json
import datetime
import threading
import herramientas.logger as logger
from herramientas.db import obtener_config, guardar_config
from herramientas.seguridad import obtener_hardware_id, cifrar_texto, descifrar_texto

DIAS_GRACIA_OFFLINE = 15
TIMEOUT_GITHUB      = 8
GITHUB_USUARIO      = "HCarranza99"
GITHUB_REPO         = "sistema-agua-licencias"
GITHUB_ARCHIVO      = "licencias.json"

_URL_LICENCIAS = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_USUARIO}/{GITHUB_REPO}/main/{GITHUB_ARCHIVO}"
)

_cache_sesion: dict | None = None


def guardar_token_github(token: str) -> bool:
    try:
        guardar_config("github_token_cifrado", cifrar_texto(token.strip()))
        return True
    except Exception as e:
        logger.registrar("licencia_online.py", "guardar_token_github", e)
        return False


def _obtener_token() -> str:
    cifrado = obtener_config("github_token_cifrado", "")
    return descifrar_texto(cifrado) if cifrado else ""


def token_configurado() -> bool:
    return bool(_obtener_token())


def _consultar_github() -> dict | None:
    token = _obtener_token()
    if not token:
        return None
    try:
        req = urllib.request.Request(_URL_LICENCIAS)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github.v3.raw")
        req.add_header("Cache-Control", "no-cache")
        with urllib.request.urlopen(req, timeout=TIMEOUT_GITHUB) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            logger.registrar("licencia_online.py", "_consultar_github",
                             Exception("Token inválido (401)"))
        elif e.code == 404:
            logger.registrar("licencia_online.py", "_consultar_github",
                             Exception("Repo o archivo no encontrado (404)"))
        return None
    except Exception:
        return None


def _guardar_cache(activa: bool, vence: str, cliente: str) -> None:
    guardar_config("online_ultima_verificacion", datetime.date.today().isoformat())
    guardar_config("online_activa",  "1" if activa else "0")
    guardar_config("online_vence",   vence)
    guardar_config("online_cliente", cliente)


def _leer_cache() -> dict | None:
    ultima = obtener_config("online_ultima_verificacion", "")
    if not ultima:
        return None
    try:
        dias = (datetime.date.today() - datetime.date.fromisoformat(ultima)).days
    except ValueError:
        return None
    if dias > DIAS_GRACIA_OFFLINE:
        return None
    return {
        "activa":            obtener_config("online_activa", "0") == "1",
        "vence":             obtener_config("online_vence", ""),
        "cliente":           obtener_config("online_cliente", ""),
        "dias_sin_conexion": dias,
        "desde_cache":       True,
    }


def verificar_licencia_online() -> dict:
    global _cache_sesion
    if _cache_sesion is not None:
        return _cache_sesion

    hardware_id  = obtener_hardware_id()
    datos_github = _consultar_github()

    if datos_github is not None:
        entrada = datos_github.get(hardware_id, {})
        activa  = bool(entrada.get("activa", False))
        vence   = entrada.get("vence", "")
        cliente = entrada.get("cliente", "")
        _guardar_cache(activa, vence, cliente)

        if not entrada:
            resultado = {
                "online_ok": True, "activa": False, "vence": "",
                "cliente": "", "dias_sin_conexion": 0, "desde_cache": False,
                "dias_gracia_restantes": 0, "bloqueado_offline": False,
                "mensaje": "Este equipo no está registrado. Contacte al desarrollador.",
            }
        elif not activa:
            resultado = {
                "online_ok": True, "activa": False, "vence": vence,
                "cliente": cliente, "dias_sin_conexion": 0, "desde_cache": False,
                "dias_gracia_restantes": 0, "bloqueado_offline": False,
                "mensaje": "❌ Suscripción suspendida. Contacte al desarrollador.",
            }
        else:
            resultado = {
                "online_ok": True, "activa": True, "vence": vence,
                "cliente": cliente, "dias_sin_conexion": 0, "desde_cache": False,
                "dias_gracia_restantes": DIAS_GRACIA_OFFLINE, "bloqueado_offline": False,
                "mensaje": f"✅ Licencia activa — {cliente}",
            }
        _cache_sesion = resultado
        return resultado

    cache = _leer_cache()

    if cache is None:
        resultado = {
            "online_ok": False, "activa": False, "vence": "", "cliente": "",
            "dias_sin_conexion": DIAS_GRACIA_OFFLINE + 1, "desde_cache": True,
            "dias_gracia_restantes": 0, "bloqueado_offline": True,
            "mensaje": (
                f"❌ Sin conexión y el período de gracia ({DIAS_GRACIA_OFFLINE} días) "
                "expiró.\nConecte a internet para verificar la licencia."
            ),
        }
        _cache_sesion = resultado
        return resultado

    dias_sin  = cache["dias_sin_conexion"]
    dias_rest = DIAS_GRACIA_OFFLINE - dias_sin

    if not cache["activa"]:
        resultado = {
            "online_ok": False, "activa": False, "vence": cache["vence"],
            "cliente": cache["cliente"], "dias_sin_conexion": dias_sin,
            "desde_cache": True, "dias_gracia_restantes": dias_rest,
            "bloqueado_offline": False,
            "mensaje": "❌ Suscripción suspendida (último estado conocido).",
        }
    else:
        resultado = {
            "online_ok": False, "activa": True, "vence": cache["vence"],
            "cliente": cache["cliente"], "dias_sin_conexion": dias_sin,
            "desde_cache": True, "dias_gracia_restantes": dias_rest,
            "bloqueado_offline": False,
            "mensaje": (
                f"⚠️ Sin internet — licencia en caché.\n"
                f"Días de gracia restantes: {dias_rest}."
            ),
        }

    _cache_sesion = resultado
    return resultado


def verificar_en_background(callback=None) -> None:
    def _worker():
        global _cache_sesion
        _cache_sesion = None
        resultado = verificar_licencia_online()
        if callback:
            try:
                callback(resultado)
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True).start()


def limpiar_cache_sesion() -> None:
    global _cache_sesion
    _cache_sesion = None