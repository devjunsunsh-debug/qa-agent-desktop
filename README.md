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