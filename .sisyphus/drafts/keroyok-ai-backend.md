# Keroyok.AI Backend Planning Draft

## User Goal
- Build the AI backend for Keroyok.AI, an agentic AI project manager app.
- Initial agent families proposed by user:
  - Talent Acquisition (OUT OF SCOPE for MVP)
  - PM Agent (IN SCOPE - first deliverable)
  - Secretary (OUT OF SCOPE for MVP)

## Business Context
- Target: Indonesian freelancers entering global remote work.
- Core value: AI-managed micro-agencies with PM + soft-skills copilot behavior.

---

## Interview Answers (ALL LOCKED)

### Q: Current app stack?
**A:** Python (FastAPI/Django) + Next.js — existing backend (FastAPI/Django) + frontend (Next.js).

### Q: First backend deliverable?
**A:** PM Agent (Recommended) — the core differentiator.

### Q: AI model/provider?
**A:** Azure AI Foundry.

### Q: Agent orchestration?
**A:** Microsoft Agent SDK (direct requirement — NOT LangChain/LangGraph/CrewAI).

### Q: Memory/persistence?
**A:** Vector DB from day one.

### Q: Done criteria?
**A:** Agents answer correctly in isolation (not full E2E).

### Q1: Which Vector DB?
**A:** Azure AI Search.

### Q2: Azure AI Foundry Deployment Details?
**A:** Set endpoint resource template first. Deploy GPT-4.1 later (user will do manually).

### Q3: Context Bank Communication Pattern?
**A:** Shared tool-based context — each subagent reads/writes to a central store via tools.

---

## PM Agent Scope (MVP)

### Subagents:
1. **Task Breakdown** — Parse user document → break into small tasks based on freelancer availability.
2. **Work Checker** — Check completed work against scope, return references/improvements.
3. **Reporter** — Generate weekly reports, project health updates every N days, escalation tickets.

### Main Tool:
- **Context Bank** — Shared vector-backed memory (Azure AI Search) + JSON store. All subagents read/write via tools. Keeps entire PM agent coherent.

### OUT of MVP scope:
- Talent Acquisition Agent (signup/CV/matchmaking)
- Secretary Agent (MoM/chat summarization/chatbot)
- Frontend integration (E2E not required)
- Production deployment
- Actual GPT-4.1 deployment (endpoint template only for now)

---

## Technical Decisions (ALL CONFIRMED)

| Decision | Value |
|----------|-------|
| Backend | FastAPI (existing) + AI layer |
| AI Provider | Azure AI Foundry (endpoint template now, GPT-4.1 later) |
| Orchestration | Microsoft Agent SDK |
| Memory/Vector DB | Azure AI Search |
| Communication | Shared tool-based context |
| Success metric | Agents answer correctly in isolation |

---

## Open Items (Exploration-Dependent)
- Existing FastAPI route/controller patterns
- How to structure the Agent SDK integration into FastAPI
- Azure AI Search index schema design
- Test strategy (pending exploration)
- Agent SDK version/configuration

## Latest User Decisions
- Vector DB: Azure AI Search
- Azure AI Foundry: create endpoint resource template first; actual GPT-4.1 deployment later
- Inter-agent communication: shared tool-based context

## Exploration Recovery
- Initial broad explore tasks timed out with no usable findings.
- Re-grounding with narrower repo inspection before plan generation.
- Repo root currently contains only `.sisyphus/`; no application/backend files discovered yet.
