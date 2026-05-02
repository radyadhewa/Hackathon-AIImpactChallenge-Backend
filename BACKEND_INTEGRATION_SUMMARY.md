# Backend API Integration Summary

**Date:** 2026-05-02  
**Backend Status:** ✅ Ready for Frontend Integration  
**Base URL:** `http://127.0.0.1:8000`

---

## 1. Health Check

Before integrating, verify the backend is healthy:

```bash
curl http://127.0.0.1:8000/api/v1/pm/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "runtime": "local-template-runtime",  // or "azure-ai-foundry" if configured
  "context_bank": "cosmos-db",      // or "local-json-only"
  "log_store": "local-json",       // or "cosmos-db"
  "azure_search": "disabled",    // or "connected", "configured_not_ready"
  "cors_origins": ["http://localhost:3000", "http://127.0.0.1:3000"]
}
```

---

## 2. Endpoint Compatibility Matrix

### A. PM Agent Endpoints

| # | Endpoint | Method | Payload from Frontend | Backend Status | Notes |
|---|----------|--------|---------------------|----------------|-------|
| 1 | `/api/v1/pm/projects/bootstrap` | POST | `overview: { project_id, project_name, ... }` | ✅ **MATCHES** | Response has `snapshot` field |
| 2 | `/api/v1/pm/projects/{projectId}/context` | GET | (none) | ✅ **MATCHES** | Returns `snapshot` with `overview`, `recent_entries` |
| 3 | `/api/v1/pm/task-breakdown` | POST | `project_id`, `delivery_goal`, `source_material`, `freelancer_focus` | ✅ **MATCHES** | All fields accepted |
| 4 | `/api/v1/pm/timeline/generate` | POST | `project_id`, `start_date` | ✅ **MATCHES** | `start_date` is optional |
| 5 | `/api/v1/pm/projects/{projectId}/timeline` | GET | (none) | ✅ **MATCHES** | Response: `timeline.entries[]` |
| 6 | `/api/v1/pm/reports` | POST | `project_id`, `cadence`, `days_since_last_report`, `requester_notes` | ✅ **MATCHES** | All fields accepted including typo |

**Frontend Response Parsing:**
```javascript
// For #1, #2
const snapshot = data?.snapshot;

// For #3
const result = data?.result?.tasks;  // TaskBreakdownResult

// For #4, #5
const timelineEntries = data?.timeline?.entries || [];
```

### B. Secretary Agent Endpoints

| # | Endpoint | Method | Payload from Frontend | Backend Status | Notes |
|---|----------|--------|---------------------|----------------|-------|
| 1 | `/api/v1/secretary/projects/{projectId}/conversations` | GET | (none) | ✅ **MATCHES** | Returns array directly |
| 2 | `/api/v1/secretary/messages` | POST | `project_id`, `conversation_id`, `sender_type`, `sender_id`, `sender_name`, `content`, `reply_to` | ✅ **MATCHES** | All fields accepted |
| 3 | `/api/v1/secretary/chat/history` | POST | `conversation_id`, `limit`, `before_message_id` | ⚠️ **MISSING `project_id`** | Frontend doesn't send project_id, backend expects it |
| 4 | `/api/v1/secretary/suggest` | POST | `project_id`, `conversation_id`, `current_message`, `context_messages` | ✅ **MATCHES** | Returns `suggestions[]` |

**Action Needed for #3:** Backend requires `project_id` but frontend doesn't send it. 
- **Option A:** Fix frontend to send `project_id`
- **Option B:** Backend can infer from `conversation_id` (needs code change)

### C. Talent Acquisition Endpoints

| # | Endpoint | Method | Payload from Frontend | Backend Status | Notes |
|---|----------|--------|---------------------|----------------|-------|
| 1 | `/api/v1/talent/signup/cv` | POST | `user_id`, `email`, `full_name`, `cv_text`, `cv_format` | ✅ **MATCHES** | Returns `profile_id` |
| 2 | `/api/v1/talent/profiles/{profileId}/generate` | POST | `profile_id`, `enhance_with_ai` | ✅ **MATCHES** | Returns enhanced profile |

---

## 3. Known Issues & Solutions

### Issue 1: "Local fallback" message in frontend
**Cause:** Azure Search not connected or index not created.

**Solution:** 
- This is **expected** in local development
- Data is stored in Cosmos DB or local JSON instead
- To fix: Configure Azure Search in `.env` or ignore for development

### Issue 2: Azure Search errors in logs
```
Azure Search query failed: getaddrinfo failed
Azure Search upsert failed: The index 'keroyok-context-bank' was not found
```

**Solution:**
- Ignore for local development
- Data still works via Cosmos DB or local JSON
- Or configure: `AZURE_AI_SEARCH_ENDPOINT` and `AZURE_AI_SEARCH_API_KEY`

### Issue 3: Secretary chat/history missing project_id
**Frontend sends:** `{ conversation_id, limit, before_message_id }`  
**Backend expects:** `project_id` + `conversation_id` + ...

**Solution:** Add `project_id` to frontend payload or the backend infers it

### Issue 4: CORS errors
**If frontend can't connect:**

Check `.env`:
```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

---

## 4. Quick Test Scripts

### Test PM Endpoints
```bash
# Health check
curl http://127.0.0.1:8000/api/v1/pm/health

# Bootstrap project
curl -X POST http://127.0.0.1:8000/api/v1/pm/projects/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "overview": {
      "project_id": "test-001",
      "project_name": "Test Project",
      "description": "Test description",
      "scope": "Test scope",
      "success_criteria": ["Done"],
      "constraints": []
    }
  }'

# Get context
curl http://127.0.0.1:8000/api/v1/pm/projects/test-001/context

# Task breakdown
curl -X POST http://127.0.0.1:8000/api/v1/pm/task-breakdown \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-001",
    "delivery_goal": "Build a website",
    "source_material": "Requirements document"
  }'

# Get timeline
curl http://127.0.0.1:8000/api/v1/pm/projects/test-001/timeline
```

### Test Secretary Endpoints
```bash
# List conversations
curl http://127.0.0.1:8000/api/v1/secretary/projects/test-001/conversations

# Send message
curl -X POST http://127.0.0.1:8000/api/v1/secretary/messages \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-001",
    "conversation_id": "conv-001",
    "sender_type": "client",
    "sender_id": "user@test.com",
    "sender_name": "Test User",
    "content": "Hello"
  }'

# Get chat history
curl -X POST http://127.0.0.1:8000/api/v1/secretary/chat/history \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-001",
    "limit": 10
  }'
```

---

## 5. Environment Setup

### Required for Full Functionality (.env)
```env
# Base
APP_NAME=Keroyok.AI Backend
APP_ENV=local
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Azure AI Foundry (LLM) - Optional, uses local fallback if not set
# AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com
# AZURE_FOUNDRY_API_KEY=your-key
# AZURE_FOUNDRY_CHAT_DEPLOYMENT=gpt-4
# AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT=embedding-model

# Azure Cosmos DB (Storage) - Optional, uses local JSON if not set
# COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443
# COSMOS_KEY=your-key
# COSMOS_DATABASE=keroyok-ai
# COSMOS_CONTEXT_CONTAINER=context-bank
# COSMOS_CHAT_CONTAINER=chat-data

# Azure AI Search (Vector Search) - Optional, uses local fallback if not set
# AZURE_AI_SEARCH_ENDPOINT=https://keroyokan-vecdb.search.windows.net
# AZURE_AI_SEARCH_API_KEY=your-key
# AZURE_AI_SEARCH_INDEX_NAME=keroyok-context-bank
# AZURE_AI_SEARCH_VECTOR_DIMENSIONS=1536

# Runtime
USE_MICROSOFT_AGENT_FRAMEWORK=false  # Set true only if Azure Foundry is configured
```

### Minimal Setup (Works without Azure)
```env
# Just leave Azure sections blank or commented out
# Backend will use local fallbacks automatically
```

---

## 6. Status Summary

| Component | Status | Works Without |
|----------|--------|------------|
| PM Agent | ✅ Ready | Yes (local JSON) |
| Secretary Agent | ✅ Ready | Yes (local JSON) |
| Talent Agent | ✅ Ready | Yes (local JSON) |
| Cosmos DB | ✅ Connected | Yes (local JSON) |
| Azure AI Search | ⚠️ Not Ready | Yes (local) |
| Azure Foundry | ❌ Not Configured | Yes (local template) |

**Overall: ✅ Backend is ready for frontend integration.**

The "Local fallback" message and Azure Search errors are **expected** when running without full Azure configuration. All core functionality works with local storage.

---

## 7. Next Steps

1. **Test locally** with curl scripts above
2. **Start frontend** pointing to `http://127.0.0.1:8000`
3. **Ignore Azure Search errors** in development
4. **Deploy to Azure** later with full configuration when ready

For issues, check health endpoint first:
```bash
curl http://127.0.0.1:8000/api/v1/pm/health
```