# Keroyok.AI Backend

This repository contains the AI backend scaffold for the Keroyok.AI PM-agent MVP:

- `Task Breakdown` subagent
- `Work Checker` subagent
- `Reporter` subagent
- shared `Context Bank` backed by local JSON storage and optionally Azure AI Search
- Azure-first runtime shaped around Microsoft Agent Framework and Azure OpenAI

## Architecture

The backend is built so you can develop locally before your Azure resources are fully wired:

- `FastAPI` exposes the PM-agent endpoints.
- `PMAgentService` orchestrates the three PM subagents.
- `ContextBankService` stores project state locally and can mirror searchable memory into Azure AI Search.
- `MicrosoftAgentRuntime` is the primary chat runtime for Azure OpenAI via Microsoft Agent Framework.
- `LocalTemplateRuntime` is a safe fallback so the backend still runs before Azure credentials and deployments exist.

## Endpoints

- `POST /api/v1/pm/projects/bootstrap`
- `POST /api/v1/pm/projects/{project_id}/updates`
- `GET /api/v1/pm/projects/{project_id}/context`
- `POST /api/v1/pm/task-breakdown`
- `POST /api/v1/pm/work-check`
- `POST /api/v1/pm/reports`

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env
uvicorn app.main:app --reload
```

## Azure Setup Notes

1. Create your Azure OpenAI resource and deployment names.
2. Create your Azure AI Search service and set the index name.
3. Fill in `.env`.
4. Restart the API.

If Azure settings are incomplete, the app automatically falls back to a deterministic local runtime for developer testing.

## Example Flow

1. Bootstrap project context:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pm/projects/bootstrap ^
  -H "Content-Type: application/json" ^
  -d "{\"overview\":{\"project_id\":\"proj-demo\",\"project_name\":\"Enterprise Website Revamp\",\"description\":\"Build a multilingual B2B marketing site.\",\"scope\":\"Discovery, design QA, frontend build, CMS handoff.\",\"success_criteria\":[\"Launch in 6 weeks\",\"Mobile responsive\",\"CMS editable\"],\"constraints\":[\"Budget capped\",\"Async collaboration only\"],\"freelancers\":[{\"name\":\"Dina\",\"role\":\"Frontend Engineer\",\"hours_per_week\":20,\"timezone\":\"Asia/Jakarta\",\"skills\":[\"Next.js\",\"Tailwind\"]},{\"name\":\"Rafi\",\"role\":\"Designer\",\"hours_per_week\":12,\"timezone\":\"Asia/Jakarta\",\"skills\":[\"Figma\",\"Design systems\"]}],\"milestones\":[{\"name\":\"Design freeze\",\"due_date\":\"2026-05-15\",\"success_definition\":\"Approved UI kit\"}]}}"
```

2. Ask the PM agent to break work down:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pm/task-breakdown ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"proj-demo\",\"delivery_goal\":\"Launch MVP website\",\"source_material\":\"Client wants polished enterprise feel, CMS editing, and responsive pages for product + case studies.\"}"
```

## Code Map

- `app/main.py` app factory
- `app/api/routes/pm_agent.py` API endpoints
- `app/agents/pm_agent.py` PM-agent orchestration
- `app/agents/prompts.py` subagent instructions
- `app/services/context_bank.py` shared memory
- `app/services/azure_search.py` optional Azure AI Search vector memory adapter
- `app/services/llm.py` Microsoft Agent Framework runtime + local fallback

