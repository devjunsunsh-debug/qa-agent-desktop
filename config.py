import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".qa_agent_config.json")

def config_existe():
    """Verifica si ya existe configuracion guardada."""
    return os.path.exists(CONFIG_PATH)

def cargar_config():
    """Carga la configuracion guardada. Retorna dict o None."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None

def guardar_config(datos):
    """Guarda la configuracion en disco."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(datos, f, indent=2)
        return True
    except Exception:
        return False

def eliminar_config():
    """Elimina la configuracion (reset)."""
    try:
        if os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)
        return True
    except Exception:
        return False

def aplicar_config(config):
    """Aplica la configuracion como variables de entorno."""
    os.environ["AZURE_ORG"] = config.get("azure_org", "")
    os.environ["AZURE_PROJECT"] = config.get("azure_project", "")
    os.environ["AZURE_PAT"] = config.get("azure_pat", "")
    os.environ["ANTHROPIC_API_KEY"] = config.get("anthropic_key", "")