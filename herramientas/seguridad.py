import hashlib
import hmac
import uuid
import base64
import platform
import subprocess


# =============================================================================
# CONTRASEÑAS
# =============================================================================

def hashear_contrasena(contrasena: str) -> str:
    """SHA-256 de la contraseña en texto plano."""
    return hashlib.sha256(contrasena.encode("utf-8")).hexdigest()


def validar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return hashear_contrasena(contrasena) == hash_guardado


# =============================================================================
# CIFRADO SIMPLE PARA DATOS SENSIBLES (SMTP, etc.)
# =============================================================================

_CIFRADO_KEY = b"SistemaAguaADESCO2025SecretKey!!"  # 32 bytes


def cifrar_texto(texto: str) -> str:
    """Cifrado XOR simple para guardar contraseñas SMTP en la BD."""
    encoded = texto.encode("utf-8")
    key = (_CIFRADO_KEY * ((len(encoded) // len(_CIFRADO_KEY)) + 1))[:len(encoded)]
    cifrado = bytes(a ^ b for a, b in zip(encoded, key))
    return base64.b64encode(cifrado).decode("utf-8")


def descifrar_texto(texto_cifrado: str) -> str:
    """Descifra un texto cifrado con cifrar_texto."""
    try:
        cifrado = base64.b64decode(texto_cifrado.encode("utf-8"))
        key = (_CIFRADO_KEY * ((len(cifrado) // len(_CIFRADO_KEY)) + 1))[:len(cifrado)]
        return bytes(a ^ b for a, b in zip(cifrado, key)).decode("utf-8")
    except Exception:
        return ""


# =============================================================================
# HARDWARE ID (para vincular licencia a una PC)
# =============================================================================

_hardware_id_cache = None


def obtener_hardware_id() -> str:
    """
    Genera un identificador unico de la PC combinando informacion del hardware.
    Es consistente entre reinicios en la misma maquina.
    El resultado se cachea en memoria para no relanzar wmic multiples veces.
    """
    global _hardware_id_cache
    if _hardware_id_cache:
        return _hardware_id_cache

    try:
        sistema = platform.system()
        datos = []

        if sistema == "Windows":
            try:
                resultado = subprocess.check_output(
                    "wmic csproduct get uuid", shell=True,
                    stderr=subprocess.DEVNULL
                ).decode("utf-8", errors="ignore")
                uuid_val = resultado.strip().split("\n")[-1].strip()
                datos.append(uuid_val)
            except Exception:
                pass
            try:
                resultado = subprocess.check_output(
                    "wmic cpu get ProcessorId", shell=True,
                    stderr=subprocess.DEVNULL
                ).decode("utf-8", errors="ignore")
                cpu_id = resultado.strip().split("\n")[-1].strip()
                datos.append(cpu_id)
            except Exception:
                pass

        # Fallback: MAC address (mas estable que el hostname)
        try:
            datos.append(hex(uuid.getnode()))
        except Exception:
            pass

        datos.append(platform.node())
        datos.append(platform.machine())
        datos.append(platform.processor())

        raw = "|".join(filter(None, datos))
        _hardware_id_cache = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return _hardware_id_cache

    except Exception:
        _hardware_id_cache = hashlib.sha256(
            platform.node().encode("utf-8")
        ).hexdigest()[:32]
        return _hardware_id_cache


# =============================================================================
# CUENTA SOPORTE EMBEBIDA
# =============================================================================

# Clave maestra para derivar la contrasena del rol Soporte.
# NUNCA debe cambiar entre versiones ni compartirse con el cliente.
_SOPORTE_SECRET = b"ADESCO_SOPORTE_MASTER_2025_ZQ7XK"


def generar_password_soporte(hardware_id: str) -> str:
    """
    Genera la contrasena del usuario soporte derivada del hardware ID.

    Es unica por PC: el mismo hardware siempre produce la misma contrasena,
    pero es diferente en cada maquina cliente.

    Como desarrollador, calcula la contrasena de cualquier cliente con:
        from herramientas.seguridad import generar_password_soporte
        print(generar_password_soporte("<hardware_id_del_cliente>"))

    El hardware ID del cliente se ve en Panel Soporte -> "Copiar Hardware ID".
    """
    raw = hmac.new(
        _SOPORTE_SECRET, hardware_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:12].upper()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


# =============================================================================
# LICENCIAS - HMAC-SHA256
# Formato de clave: ADESCO-YYYYMM-AAAAA-BBBBB-CCCCC
#   YYYYMM  : mes de expiracion embebido directamente en la clave
#   AAAAA-BBBBB-CCCCC : 15 chars HMAC-SHA256(secret, "hw_id|YYYY-MM")
# =============================================================================

# Esta clave secreta NUNCA debe cambiar entre versiones ni compartirse.
_LICENCIA_SECRET = b"ADESCO_SISTEMA_AGUA_SECRET_2025_XK9"


def generar_clave_licencia(hardware_id: str, fecha_expiracion: str) -> str:
    """
    Genera una clave de licencia firmada con HMAC-SHA256.

    Args:
        hardware_id: ID del hardware de la PC destino (32 chars hex).
                     Usar "*" para una clave de activacion inicial
                     que se vincula al hardware la primera vez que se usa.
        fecha_expiracion: Formato YYYY-MM (ej: "2026-04")

    Returns:
        Clave en formato ADESCO-YYYYMM-AAAAA-BBBBB-CCCCC
    """
    payload = f"{hardware_id}|{fecha_expiracion}"
    firma = hmac.new(
        _LICENCIA_SECRET, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:15].upper()

    fecha_compact = fecha_expiracion.replace("-", "")  # "2026-04" -> "202604"
    bloques = [firma[i:i+5] for i in range(0, 15, 5)]
    return "ADESCO-" + fecha_compact + "-" + "-".join(bloques)


def validar_clave_licencia(clave: str, hardware_id: str) -> dict:
    """
    Valida una clave de licencia extrayendo la fecha directamente de ella.
    No lee la base de datos — rompe la dependencia circular de activacion.

    Returns:
        dict con keys:
          - valida (bool)
          - fecha_expiracion (str YYYY-MM o None)
          - mensaje (str)
    """
    try:
        clave = clave.strip().upper()
        if not clave.startswith("ADESCO-"):
            return {"valida": False, "fecha_expiracion": None,
                    "mensaje": "Formato de clave invalido."}

        partes = clave.split("-")
        # Formato: ["ADESCO", "202604", "AAAAA", "BBBBB", "CCCCC"] = 5 partes
        if len(partes) != 5:
            return {"valida": False, "fecha_expiracion": None,
                    "mensaje": "Formato de clave invalido (se esperan 5 bloques)."}

        fecha_compact = partes[1]  # "202604"
        if len(fecha_compact) != 6 or not fecha_compact.isdigit():
            return {"valida": False, "fecha_expiracion": None,
                    "mensaje": "La clave no contiene una fecha valida."}

        fecha_exp      = f"{fecha_compact[:4]}-{fecha_compact[4:]}"  # "2026-04"
        firma_recibida = "".join(partes[2:])  # 15 chars

        # Intentar con hardware_id real y con wildcard ("*")
        for hw in (hardware_id, "*"):
            payload        = f"{hw}|{fecha_exp}"
            firma_esperada = hmac.new(
                _LICENCIA_SECRET, payload.encode("utf-8"), hashlib.sha256
            ).hexdigest()[:15].upper()
            if hmac.compare_digest(firma_recibida, firma_esperada):
                return {"valida": True, "fecha_expiracion": fecha_exp,
                        "mensaje": "Licencia valida."}

        return {"valida": False, "fecha_expiracion": None,
                "mensaje": "Clave invalida o no corresponde a este equipo."}

    except Exception as e:
        return {"valida": False, "fecha_expiracion": None,
                "mensaje": f"Error al validar: {e}"}
