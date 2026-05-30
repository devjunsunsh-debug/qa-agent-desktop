import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

def get_token():
    """
    Obtiene la identidad del usuario desde Azure DevOps usando el PAT.
    Retorna (token, user_info) o (None, error_msg)
    """
    pat = os.getenv("AZURE_PAT", "")
    org = os.getenv("AZURE_ORG", "")

    if not pat or not org:
        return None, "PAT o organizacion no configurados."

    token_b64 = base64.b64encode(f":{pat}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token_b64}",
        "Content-Type": "application/json"
    }

    try:
        # Usar la API de conexion que solo requiere permisos basicos
        url = f"https://dev.azure.com/{org}/_apis/connectiondata"
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 401:
            return None, "PAT invalido o vencido. Verifica tus credenciales."
        elif response.status_code == 403:
            return None, "PAT sin permisos suficientes."
        elif response.status_code != 200:
            return None, f"Error al conectar con Azure (HTTP {response.status_code})"

        data = response.json()

        # La API de connectiondata retorna el usuario autenticado
        auth_user = data.get("authenticatedUser", {})

        user_info = {
            "name": auth_user.get("providerDisplayName", "Usuario"),
            "email": auth_user.get("properties", {}).get("Account", {}).get("$value", ""),
            "tipo": "pat"
        }

        # Si el email vino vacio intentar con el subjectDescriptor
        if not user_info["email"]:
            user_info["email"] = auth_user.get("uniqueName", "")

        return "pat_token", user_info

    except requests.exceptions.ConnectionError:
        return None, "Error de conexion. Verifica tu red."
    except requests.exceptions.Timeout:
        return None, "Timeout al conectar con Azure DevOps."
    except Exception as e:
        return None, f"Error inesperado: {str(e)}"

def cerrar_sesion():
    """Sin cache que limpiar en modo PAT."""
    pass