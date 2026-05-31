# QA Agent - Generador Automático de Test Cases

Herramienta de escritorio que usa Inteligencia Artificial para generar 
test cases profesionales en Azure DevOps a partir de Product Backlog Items (PBIs).

## ¿Qué hace?

- Conecta con Azure DevOps para obtener PBIs
- Valida que el QA esté asignado al PBI antes de proceder
- Genera test cases usando IA (Claude, DeepSeek, GPT o Gemini)
- Crea los test cases en Azure DevOps con área, iteración y pasos correctos
- Los vincula automáticamente al PBI y al Test Suite del sprint
- Muestra el ícono de test cases en el board de Azure DevOps

## Tecnologías

- Python 3.14
- Tkinter (interfaz de escritorio)
- FastAPI (próximamente)
- Azure DevOps REST API
- Anthropic Claude / DeepSeek / OpenAI GPT / Google Gemini

## Instalación

1. Clona el repositorio:

git clone https://github.com/devjunsunsh-debug/qa-agent-desktop.git

2. Instala las dependencias:

pip install anthropic openai python-dotenv requests

3. Configura tus credenciales

Edita el archivo .env y agrega tus datos:

AZURE_ORG=tuorg
AZURE_PROJECT=tuproyecto
AZURE_PAT=tuPAT
ANTHROPIC_KEY=tuAPIKey
OPENAI_API_KEY=tuAPIKey
GEMINI_API_KEY=tuAPIKey
DEEPSEEK_API_KEY=tuAPIKey
DEFAULT_PROVIDER=anthropic

4. Ejecuta la aplicación

python ui.py

## Uso

1. Inicia sesión con tu cuenta de Azure DevOps
2. Ingresa el ID del PBI
3. Click en **Analizar PBI** — el agente valida asignación y completitud
4. Revisa los test cases generados por IA
5. Click en **Crear test cases en Azure** para publicarlos

## Requisitos del PAT de Azure DevOps

El Personal Access Token debe tener estos permisos:
- Work Items: Read, write & manage
- Test Management: Read & write
- User Profile: Read & write

## Autor

Camilo Alvarado — QA Engineer  
[LinkedIn](https://www.linkedin.com/in/cristian-camilo-alvarado-beltran-973359130/) · [GitHub](https://github.com/devjunsunsh-debug)