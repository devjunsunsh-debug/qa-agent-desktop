import requests
import anthropic
import base64
import os
import json

from dotenv import load_dotenv

load_dotenv()

def get_auth_headers():
    pat = os.getenv("AZURE_PAT")
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }
def _extraer_email(campo):
    """
    El campo de identidad en Azure puede venir como:
    - Diccionario: {"uniqueName": "email@dominio.com", "displayName": "Nombre"}
    - String directo: "email@dominio.com"
    - Vacío: None o ""
    """
    if not campo:
        return ""
    if isinstance(campo, dict):
        return campo.get("uniqueName", campo.get("emailAddress", ""))
    if isinstance(campo, str):
        return campo
    return ""

def get_pbi(work_item_id):
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.0"

    response = requests.get(url, headers=get_auth_headers(), timeout=15)

    if response.status_code != 200:
        print(f"❌ Error al obtener PBI: {response.status_code}")
        print(response.text)
        return None

    fields = response.json().get("fields", {})

    pbi = {
        "id": work_item_id,
        "titulo": fields.get("System.Title", ""),
        "descripcion": fields.get("System.Description", ""),
        "criterios": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
        "asignado_a": _extraer_email(fields.get("Custom.QATesterAssigned", "")),
        "area": fields.get("System.AreaPath", ""),        # <- agregar
        "iteration": fields.get("System.IterationPath", ""),  # <- agregar
}

    # Evaluar qué tan completo está el PBI
    pbi["completitud"] = evaluar_completitud(pbi)

    return pbi

def evaluar_completitud(pbi):
    """
    Retorna un dict con el nivel de completitud y qué campos faltan.
    """
    tiene_titulo = bool(pbi["titulo"].strip())
    tiene_descripcion = bool(pbi["descripcion"].strip())
    tiene_criterios = bool(pbi["criterios"].strip())

    campos_faltantes = []
    if not tiene_descripcion:
        campos_faltantes.append("Descripción")
    if not tiene_criterios:
        campos_faltantes.append("Criterios de Aceptación")

    if tiene_titulo and tiene_descripcion and tiene_criterios:
        nivel = "completo"
    elif tiene_titulo and (tiene_descripcion or tiene_criterios):
        nivel = "parcial"
    else:
        nivel = "incompleto"

    return {
        "nivel": nivel,
        "campos_faltantes": campos_faltantes,
        "necesita_tag": nivel in ["parcial", "incompleto"] and not tiene_criterios
    }

def generate_test_cases(pbi):
    import json
    from config import cargar_config

    # ── Validación temprana ──────────────────────────────────────────
    # Si el PBI no tiene criterios de aceptación, bloqueamos la generación
    # antes de llamar a la IA. Esto ahorra tokens y da feedback inmediato.
    if not pbi.get("criterios", "").strip():
        return {
            "advertencia": (
                f"⚠️ El PBI {pbi['id']} no tiene Criterios de Aceptación definidos. "
                "Por favor completa este campo en Azure DevOps antes de generar test cases."
            ),
            "test_cases": []
        }, None
    # ────────────────────────────────────────────────────────────────

    config = cargar_config() or {}
    proveedor = config.get("ia_provider", "Anthropic (Claude)")
    api_key = config.get("anthropic_key", os.getenv("ANTHROPIC_API_KEY", ""))

    prompt = f"""Eres un QA Engineer Senior especializado en pruebas manuales de software empresarial.
Tu responsabilidad es generar Test Cases profesionales, claros y ejecutables.

INFORMACIÓN DEL PBI:
- ID: {pbi['id']}
- Título: {pbi['titulo']}
- Descripción: {pbi['descripcion'] or 'No proporcionada'}
- Criterios de Aceptación: {pbi['criterios'] or 'No proporcionados'}

REGLA CRÍTICA ANTES DE GENERAR:
Si el campo "Criterios de Aceptación" está vacío, dice "No proporcionados", o no contiene
criterios claros y verificables, NO generes test cases. En su lugar, retorna el JSON con
"test_cases" vacío y en "advertencia" explica que el PBI no tiene criterios de aceptación
definidos y que deben ser completados antes de generar test cases.

INSTRUCCIONES PARA GENERAR LOS TEST CASES (solo si hay criterios definidos):

1. Crea exactamente UN test case por cada criterio de aceptación identificado.

2. Cada test case debe cubrir en sus pasos:
   - Flujo positivo: el escenario donde todo funciona correctamente.
   - Flujo negativo: el escenario donde algo falla y el sistema debe responder bien.
   - Caso borde si aplica: situaciones límite como campos vacíos, datos extremos, etc.

3. Cada paso debe tener:
   - Una acción clara y específica que el QA debe ejecutar.
   - Un resultado esperado observable y verificable.

4. El título de cada test case debe seguir EXACTAMENTE este formato:
   "{pbi['id']} - [nombre descriptivo del criterio en máximo 8 palabras] - AC[número]"
   
   Ejemplo: "74605 - Validar ubicación automática de registros en calendario - AC1"
   
   IMPORTANTE: Nunca uses corchetes en el título final. Reemplaza [nombre] y [número]
   con los valores reales.

REGLAS DE CALIDAD:
- Los pasos deben ser tan claros que cualquier persona pueda ejecutarlos sin conocer el sistema.
- Evita pasos ambiguos como "verificar que funciona" — sé específico sobre qué verificar.
- El resultado esperado debe describir exactamente qué debe ver o experimentar el usuario.
- Mínimo 4 pasos por test case, máximo 8.

Responde ÚNICAMENTE con un JSON válido, sin texto adicional, sin bloques de código, con esta estructura exacta:

{{
  "advertencia": "string o null",
  "test_cases": [
    {{
      "titulo": "título del test case",
      "pasos": [
        {{
          "accion": "descripción clara de la acción a ejecutar",
          "resultado_esperado": "qué debe ocurrir exactamente"
        }}
      ]
    }}
  ]
}}"""
    try:
        raw = _llamar_ia(proveedor, api_key, prompt)
    except Exception as e:
        return None, f"Error con {proveedor}: {str(e)}"

    try:
        data = json.loads(raw)
        return data, None
    except json.JSONDecodeError:
        return None, f"Respuesta de IA invalida: {raw[:200]}"


def _llamar_ia(proveedor, api_key, prompt):
    if proveedor == "Anthropic (Claude)":
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,  # era 2000, duplicamos
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    elif proveedor == "DeepSeek":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=4000,  # era 2000, duplicamos
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
        

def create_test_case_in_azure(pbi, test_case, es_primero=False):
    """
    Crea un Test Case en Azure DevOps y lo vincula al PBI.
    Si es el primer TC y existe un TC manual marcador, lo sobreescribe
    en lugar de crear uno nuevo — así evitamos TCs huérfanos en el historial.
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # ── Reutilizar TC manual si es el primero ───────────────────────
    # Cuando el QA crea un TC manual para inicializar el Test Suite,
    # el agente lo detecta y lo sobreescribe con el primer TC real
    # en lugar de crear uno nuevo y dejar el manual como huérfano.
    if es_primero:
        tc_manual_id, _ = buscar_tc_manual(pbi["id"])
        if tc_manual_id:
            tc_id, error = sobreescribir_tc(tc_manual_id, pbi, test_case)
            if tc_id:
                plan_id, root_suite_id = buscar_plan_por_iteracion(
                    pbi.get("iteration", ""),
                    pbi.get("area", "")
                )
                if plan_id:
                    suite_id, _ = buscar_o_crear_suite_para_pbi(
                        plan_id, root_suite_id, pbi
                    )
                    if suite_id:
                        agregar_tc_a_suite(plan_id, suite_id, tc_id)
                    else:
                        agregar_tc_a_suite(plan_id, root_suite_id, tc_id)
                return tc_id, None
    # ────────────────────────────────────────────────────────────────

    # Flujo normal: construir XML de pasos para el nuevo TC
    steps_xml = '<steps id="0" last="{}">'.format(len(test_case["pasos"]))
    for i, paso in enumerate(test_case["pasos"], 1):
        steps_xml += f'''<step id="{i}" type="ActionStep">
            <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{paso["accion"]}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>
            <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{paso["resultado_esperado"]}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>
            <description/>
        </step>'''
    steps_xml += '</steps>'

    # El título ya incluye el ID del PBI porque el prompt lo genera con ese formato.
    # Solo usamos el título tal como lo retorna la IA sin agregar el ID nuevamente.
    titulo_completo = test_case['titulo']
    payload = [
        {"op": "add", "path": "/fields/System.Title", "value": titulo_completo},
        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml},
        {"op": "add", "path": "/fields/System.State", "value": "Design"},
        {"op": "add", "path": "/fields/System.AreaPath", "value": pbi["area"]},
        {"op": "add", "path": "/fields/System.IterationPath", "value": pbi["iteration"]}
    ]

    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Test%20Case?api-version=7.0"
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json-patch+json"

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.exceptions.ConnectionError:
        return None, "Error de conexion: no se pudo conectar a Azure DevOps. Verifica tu red."
    except requests.exceptions.Timeout:
        return None, f"Timeout: Azure no respondio al crear '{test_case['titulo']}'."
    except requests.exceptions.RequestException as e:
        return None, f"Error de red inesperado: {str(e)}"

    if response.status_code not in [200, 201]:
        return None, f"Azure rechazo la creacion (HTTP {response.status_code}): {response.text[:200]}"

    tc_id = response.json()["id"]

    # Vincular el TC al PBI mediante la relación TestedBy
    error_vinculo = vincular_tc_a_pbi(pbi["id"], tc_id)
    if error_vinculo:
        return tc_id, f"Creado (ID {tc_id}) pero no se pudo vincular: {error_vinculo}"

    # Agregar al Test Suite del sprint correspondiente
    plan_id, root_suite_id = buscar_plan_por_iteracion(
        pbi.get("iteration", ""),
        pbi.get("area", "")
    )
    if plan_id:
        suite_id, _ = buscar_o_crear_suite_para_pbi(plan_id, root_suite_id, pbi)
        if suite_id:
            agregar_tc_a_suite(plan_id, suite_id, tc_id)
        else:
            # Fallback: si no se puede crear suite propio, usar el suite raíz
            agregar_tc_a_suite(plan_id, root_suite_id, tc_id)

    return tc_id, None

def vincular_tc_a_pbi(pbi_id, tc_id):
    """Vincula el TC al PBI creando la relación desde el PBI."""
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Patcheamos el PBI, no el TC
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{pbi_id}?api-version=7.0"
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json-patch+json"

    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "Microsoft.VSTS.Common.TestedBy-Forward",  # PBI -> TC
                "url": f"https://dev.azure.com/{org}/_apis/wit/workitems/{tc_id}"
            }
        }
    ]

    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        if response.status_code not in [200, 201]:
            return f"HTTP {response.status_code}: {response.text[:200]}"
        return None
    except requests.exceptions.ConnectionError:
        return "Error de conexion al vincular"
    except requests.exceptions.Timeout:
        return "Timeout al vincular"
    except requests.exceptions.RequestException as e:
        return str(e)

def buscar_tc_manual(pbi_id):
    """
    Busca un Test Case vinculado al PBI que sea el marcador manual.
    Lo identifica porque su título es 'Test' o no tiene pasos definidos.
    Retorna (tc_id, error) o (None, None) si no encuentra ninguno.
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Obtenemos el PBI con sus relaciones para ver los TCs vinculados
    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{pbi_id}"
        f"?$expand=relations&api-version=7.0"
    )

    try:
        response = requests.get(url, headers=get_auth_headers(), timeout=15)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        relations = response.json().get("relations", [])

        # Filtramos solo las relaciones de tipo "Tested By" (TCs vinculados al PBI)
        tc_ids = [
            r["url"].split("/")[-1]
            for r in relations
            if r.get("rel") == "Microsoft.VSTS.Common.TestedBy-Forward"
        ]

        if not tc_ids:
            return None, None

        # Revisamos cada TC para encontrar el marcador manual
        for tc_id in tc_ids:
            url_tc = (
                f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{tc_id}"
                f"?api-version=7.0"
            )
            res = requests.get(url_tc, headers=get_auth_headers(), timeout=15)
            if res.status_code != 200:
                continue

            fields = res.json().get("fields", {})
            titulo = fields.get("System.Title", "").strip().lower()
            pasos = fields.get("Microsoft.VSTS.TCM.Steps", "")

            # Es el TC manual si su título es "test" o no tiene pasos
            if titulo == "test" or not pasos:
                return tc_id, None

        return None, None

    except Exception as e:
        return None, str(e)

def sobreescribir_tc(tc_id, pbi, test_case):
    """
    Sobreescribe un Test Case existente con los datos del primer TC generado por IA.
    Usa PATCH en lugar de POST porque el TC ya existe — solo actualizamos sus campos.
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Construimos el XML de pasos igual que en create_test_case_in_azure
    steps_xml = '<steps id="0" last="{}">'.format(len(test_case["pasos"]))
    for i, paso in enumerate(test_case["pasos"], 1):
        steps_xml += f'''<step id="{i}" type="ActionStep">
            <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{paso["accion"]}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>
            <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{paso["resultado_esperado"]}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>
            <description/>
        </step>'''
    steps_xml += '</steps>'

    payload = [
        {"op": "add", "path": "/fields/System.Title",
         "value": test_case["titulo"]},
        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps",
         "value": steps_xml},
        {"op": "add", "path": "/fields/System.State",
         "value": "Design"},
        {"op": "add", "path": "/fields/System.AreaPath",
         "value": pbi["area"]},
        {"op": "add", "path": "/fields/System.IterationPath",
         "value": pbi["iteration"]},
    ]

    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{tc_id}"
        f"?api-version=7.0"
    )
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json-patch+json"

    try:
        # PATCH actualiza un recurso existente — diferente a POST que crea uno nuevo
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        if response.status_code in [200, 201]:
            return tc_id, None
        return None, f"HTTP {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return None, str(e)

def buscar_plan_por_iteracion(iteration_path, area_path):
    """
    Busca el Test Plan que corresponde al IterationPath y AreaPath del PBI.
    Itera sobre todas las páginas de planes para no perderse ninguno,
    ya que Azure DevOps devuelve máximo 50 planes por página.
    Retorna (plan_id, root_suite_id) o (None, None) si no encuentra.
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Normalizar: extraer solo la última parte de la ruta
    # Funciona con ambos separadores: "Colibri\SP-A-2606" o "Colibri\\SP-A-2606"
    iter_key = iteration_path.replace("\\", "/").split("/")[-1].lower()
    area_key = area_path.replace("\\", "/").split("/")[-1].lower()

    skip = 0
    page_size = 50

    while True:
        url = (
            f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans"
            f"?api-version=7.0&$top={page_size}&$skip={skip}"
        )

        try:
            response = requests.get(url, headers=get_auth_headers(), timeout=15)
            if response.status_code != 200:
                return None, None

            plans = response.json().get("value", [])

            if not plans:
                return None, None

            # Buscar el plan que coincida con la iteración y área del PBI
            for plan in plans:
                plan_iter = plan.get("iteration", "").replace("\\", "/").split("/")[-1].lower()
                plan_area = plan.get("areaPath", "").replace("\\", "/").split("/")[-1].lower()

                if plan_iter == iter_key and plan_area == area_key:
                    return plan["id"], plan["rootSuite"]["id"]

            # Si la página vino incompleta, no hay más páginas
            if len(plans) < page_size:
                return None, None

            # Avanzar a la siguiente página
            skip += page_size

        except Exception:
            return None, None


def buscar_o_crear_suite_para_pbi(plan_id, root_suite_id, pbi):
    """
    Busca un Test Suite existente para el PBI dentro del plan.
    Si no existe, intenta crearlo. Requiere licencia Basic + Test Plans
    para la creación — si falla, el llamador usa el suite raíz como fallback.
    Retorna (suite_id, error).
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Buscar si ya existe un suite para este PBI en el plan
    url = f"https://dev.azure.com/{org}/{project}/_apis/testplan/Plans/{plan_id}/suites?api-version=7.0"

    try:
        response = requests.get(url, headers=get_auth_headers(), timeout=15)
        if response.status_code == 200:
            for suite in response.json().get("value", []):
                # Azure nombra el suite con el ID del PBI al inicio
                if str(pbi["id"]) in suite.get("name", ""):
                    return suite["id"], None
    except Exception:
        pass

    # No existe — intentar crear un suite de tipo requirementTestSuite
    # Este tipo vincula el suite directamente al PBI como requisito
    url_create = f"https://dev.azure.com/{org}/{project}/_apis/testplan/Plans/{plan_id}/suites?api-version=7.0"
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    payload = {
        "suiteType": "requirementTestSuite",
        "requirementId": pbi["id"],
        "parentSuite": {"id": root_suite_id}
    }

    try:
        response = requests.post(url_create, headers=headers, json=payload, timeout=15)
        if response.status_code in [200, 201]:
            return response.json()["id"], None
        return None, f"HTTP {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return None, str(e)


def agregar_tc_a_suite(plan_id, suite_id, tc_id):
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    url = f"https://dev.azure.com/{org}/{project}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase?api-version=7.0"
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    payload = [{"testCase": {"id": str(tc_id)}}]

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code in [200, 201]:
            return None
        return f"HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return str(e)

def agregar_tag_pbi(work_item_id, tag):
    """Agrega un tag al PBI sin borrar los tags existentes."""
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    # Primero leemos los tags actuales del PBI
    url_get = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.0"
    response = requests.get(url_get, headers=get_auth_headers(), timeout=15)

    tags_actuales = ""
    if response.status_code == 200:
        tags_actuales = response.json().get("fields", {}).get("System.Tags", "")

    # Verificar si el tag ya existe para no duplicarlo
    tags_lista = [t.strip() for t in tags_actuales.split(";") if t.strip()]
    if tag in tags_lista:
        print(f"  ℹ️  El tag '{tag}' ya existe en el PBI.")
        return True

    # Agregar el nuevo tag a los existentes
    tags_nuevos = "; ".join(tags_lista + [tag])

    url_patch = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.0"
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json-patch+json"

    payload = [
        {"op": "add", "path": "/fields/System.Tags", "value": tags_nuevos}
    ]

    response = requests.patch(url_patch, headers=headers, json=payload, timeout=15)

    if response.status_code in [200, 201]:
        print(f"  🏷️  Tag '{tag}' agregado al PBI {work_item_id}")
        return True
    else:
        print(f"  ❌ Error al agregar tag: {response.status_code}")
        return False

def tiene_test_cases(work_item_id):
    """
    Verifica si el PBI ya tiene test cases vinculados.
    Retorna (cantidad, error)
    """
    org = os.getenv("AZURE_ORG")
    project = os.getenv("AZURE_PROJECT")

    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}?$expand=relations&api-version=7.0"

    try:
        response = requests.get(url, headers=get_auth_headers(), timeout=15)
    except requests.exceptions.ConnectionError:
        return None, "Error de conexion al verificar test cases."
    except requests.exceptions.Timeout:
        return None, "Timeout al verificar test cases."

    if response.status_code != 200:
        return None, f"Error HTTP {response.status_code}"

    relations = response.json().get("relations", [])

    # Filtrar solo las relaciones de tipo "Tested By" (test cases vinculados)
    test_cases = [
        r for r in relations
        if r.get("rel") == "Microsoft.VSTS.Common.TestedBy-Forward"
    ]

    return len(test_cases), None

def validar_asignacion(pbi, email_usuario):
    asignado_a = pbi.get("asignado_a", "").strip()

    if not asignado_a:
        return False, "Sin asignar"

    nombre_usuario = email_usuario.split("@")[0].lower()  # "calvarado"
    asignado_lower = asignado_a.lower()                   # "camilo a alvarado"
    email_lower = email_usuario.lower()

    # Comparacion 1: email completo
    if email_lower in asignado_lower or asignado_lower in email_lower:
        return True, asignado_a

    # Comparacion 2: alias exacto en el campo
    if nombre_usuario in asignado_lower:
        return True, asignado_a

    # Comparacion 3: reconstruir iniciales desde el nombre asignado
    # "camilo a alvarado" -> partes = ["camilo", "a", "alvarado"]
    # inicial de cada parte -> "c", "a", "a" -> alias candidato = "calvarado" (c + alvarado)
    partes_nombre = asignado_lower.split()
    if len(partes_nombre) >= 2:
        # Patron: primera(s) inicial(es) + ultimo apellido
        # ej: "camilo a alvarado" -> "c" + "alvarado" = "calvarado" ✓
        ultimo = partes_nombre[-1]
        for i in range(len(partes_nombre) - 1):
            prefijo = "".join(p[0] for p in partes_nombre[:i+1])
            candidato = prefijo + ultimo
            if candidato == nombre_usuario:
                return True, asignado_a

    return False, asignado_a