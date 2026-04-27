# Keroyok.AI Backend

Agentic AI-powered talent marketplace with 3 integrated agents: Talent Acquisition, PM (Project Manager), and Secretary.

## Installation

### 1. Clone and create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -e .[dev]
```

### 3. Configure environment

```bash
copy .env.example .env
```

Edit `.env` with your settings. See Azure Setup section below.

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000`

## Azure Setup (Optional)

The backend works locally without Azure. To enable AI features:

1. **Azure OpenAI** - Create resource and deployment:
   - `AZURE_OPENAI_ENDPOINT` - e.g., `https://your-resource.openai.azure.com/`
   - `AZURE_OPENAI_API_KEY` - Your API key
   - `AZURE_OPENAI_CHAT_DEPLOYMENT` - Chat model deployment name
   - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` - Embedding model name

2. **Azure AI Search** - For vector search:
   - `AZURE_AI_SEARCH_ENDPOINT` - e.g., `https://your-search-service.search.windows.net`
   - `AZURE_AI_SEARCH_API_KEY` - Your search API key
   - `AZURE_AI_SEARCH_INDEX_NAME` - Index name (default: `keroyok-context-bank`)

If Azure settings are incomplete, the app falls back to a deterministic local runtime.

## Codebase Architecture

```
app/
├── main.py                    # FastAPI app factory
├── core/
│   ├── config.py             # Settings (environment variables)
│   └── dependencies.py      # Service dependency injection
├── models/
│   ├── domain.py             # Core data models
│   └── api.py                 # Request/response schemas
├── agents/
│   ├── pm_agent.py            # PM Agent orchestration
│   ├── talent_agent.py        # Talent Agent orchestration
│   ├── secretary_agent.py    # Secretary Agent orchestration
│   └── prompts.py            # Subagent instruction prompts
├── services/
│   ├── llm.py                 # LLM runtime (Azure + local)
│   ├── context_bank.py       # Project memory storage
│   ├── chat_service.py       # Chat/conversation storage
│   ├── profile_service.py   # Freelancer profile & matching
│   ├── timeline_service.py   # Project scheduling
│   └── azure_search.py       # Azure AI Search adapter
└── api/routes/
    ├── pm_agent.py            # PM Agent endpoints
    ├── talent_agent.py       # Talent Agent endpoints
    └── secretary_agent.py   # Secretary Agent endpoints
```

## How the 3 Agents Work Together

```
┌─────────────────────────────────────────────────────────────┐
│                    KERoyok.AI BACKEND                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Agent 1     │  │  Agent 2     │  │  Agent 3     │        │
│  │  TALENT     │  │  PM          │  │  SECRETARY  │        │
│  │              │  │              │  │              │        │
│  │ • CV Parser  │  │ • Task Break │  │ • Chat Summ  │        │
│  │ • Profile Gen│  │ • Work Check │  │ • MoM Gen    │        │
│  │ • Matchmake │  │ • Reporter   │  │ • Chatbot    │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                 │
│              ┌────────────┴────────────┐                   │
│              │      CONTEXT BANK        │                    │
│              │  - Project memory         │                   │
│              │  - Timelines              │                   │
│              │  - Agent events           │                   │
│              │  - Freelancer profiles   │                   │
│              │  - Chat history           │                   │
│              └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Agent 1: Talent Acquisition
- **CV Parser** - Converts resume/CV text to structured profile
- **Profile Generator** - AI-enhances profile headline and bio
- **Matchmaking** - Vector similarity matching for projects

### Agent 2: PM (Project Manager)
- **Task Breakdown** - Converts project scope into actionable tasks
- **Work Checker** - Validates deliverables against scope
- **Reporter** - Generates project health reports
- **Timeline** - Critical path scheduling

### Agent 3: Secretary
- **Chat Summarizer** - Extracts decisions and action items from chat
- **MoM Generator** - Creates minutes from meeting transcripts
- **Chatbot Assistant** - Suggests response options

## Key Concepts

### Context Bank
All agents write to a shared **Context Bank** - local JSON storage backed by Azure AI Search. This serves as the audit trail and cross-agent communication layer.

### Agent Events
When Secretary or Talent agents create action items, they write **AgentEvent** records to the Context Bank. The PM Agent reads these events and responds.

### Embeddings
Freelancer profiles and project descriptions are embedded for semantic matching using Azure OpenAI embeddings.

## Documentation

- **API Usage Guide**: [`api-usage.md`](./api-usage.md) - Full endpoint reference, payloads, response shapes, and data models
- **Development Logs**: [`.sisyphus/progress/`](.sisyphus/progress/) - Session-by-session implementation notes

## Running Tests

```bash
pytest tests/ -v
```

## Tech Stack

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation
- **Azure OpenAI** - LLM embeddings and chat
- **Azure AI Search** - Vector similarity search
- **Python 3.11+** - Runtime