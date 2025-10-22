import json
import hashlib
def surrogate_key(values: dict) -> str:
    """
    Genera una clave sustituta determinista para un dict de valores.
    - Ordena las claves (json.dumps sort_keys=True) para que el orden no afecte.
    - Usa separators compactos para evitar espacios.
    - Usa default=str para serializar tipos no JSON-serializables.
    - Devuelve MD5 hex digest de la representación canónica UTF-8.
    """
    # Normalizar None a null en JSON y asegurar orden de claves
    canonical = json.dumps(values, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.md5(canonical.encode('utf-8')).hexdigest()