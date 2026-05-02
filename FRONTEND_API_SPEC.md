# Frontend API Consumption Specification
**Date:** 2026-05-02  
**Frontend Repo:** `Hackathon-MSFTDicoding-FrontEnd`  
**Target Backend:** `http://127.0.0.1:8000` (Local) / Azure Function  

This document outlines exactly how the Next.js frontend consumes the backend APIs. Use this to align the backend response shapes and fix any payload mismatches.

---

## 1. Configuration & Environment

**Base URL:** Defined in `.env.local`
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

**API Prefix:** `/api/v1` (handled automatically by `src/app/lib/api.js`)

**Session Management:**
- `project_id` is stored in `localStorage` via `src/app/lib/workspace-session.js`
- Key used: `keroyok-ai-workspace-session`
- When a project is created, the UUID is saved to the session and used for subsequent requests.

---

## 2. API Endpoints Used by Frontend

### A. PM Agent Endpoints

#### 1. Bootstrap Project
- **Frontend Location:** `src/app/home/client/_components/ClientProjectForm.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/pm/projects/bootstrap`
- **Payload Sent:**
  ```json
  {
    "overview": {
      "project_id": "uuid-generated-client-side",
      "project_name": "Project Name",
      "client_name": "John Doe",
      "description": "Project Description",
      "scope": "Project Scope",
      "success_criteria": ["Criteria 1", "Criteria 2"],
      "constraints": ["Constraint 1"],
      "freelancers": [
        {
          "name": "Role candidate",
          "role": "Frontend Engineer",
          "hours_per_week": 20,
          "timezone": "Asia/Jakarta",
          "skills": ["React", "Next.js"],
          "notes": null
        }
      ],
      "milestones": [
        {
          "name": "Milestone 1",
          "due_date": "2026-05-15",
          "success_definition": "Definition"
        }
      ],
      "timeline_notes": "Notes here"
    }
  }
  ```
- **Expected Response:** `ProjectContextResponse` (specifically `result.snapshot.project_id`)

#### 2. Get Project Context
- **Frontend Location:** `src/app/_hooks/useProject.js`
- **Method:** `GET`
- **Endpoint:** `/api/v1/pm/projects/${projectId}/context`
- **Expected Response:**
  ```json
  {
    "snapshot": {
      "project_id": "...",
      "overview": { ... },
      "recent_entries": [ ... ]
    }
  }
  ```

#### 3. Generate Task Breakdown
- **Frontend Location:** `src/app/dashboard/client/_components/ClientOverviewPage.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/pm/task-breakdown`
- **Payload Sent:**
  ```json
  {
    "project_id": "proj-uuid",
    "delivery_goal": "Complete project delivery",
    "source_material": "Scope text here",
    "freelancer_focus": ["Frontend Engineer", "Designer"]
  }
  ```
- **Note:** Frontend currently uses `apiFetcher` directly for this. Ensure backend accepts `delivery_goal` (matches docs).

#### 4. Generate Timeline
- **Frontend Location:** `src/app/dashboard/client/_components/ClientOverviewPage.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/pm/timeline/generate`
- **Payload Sent:**
  ```json
  {
    "project_id": "proj-uuid",
    "start_date": "2026-05-02T10:00:00.000Z"
  }
  ```

#### 5. Get Timeline (Kanban Board)
- **Frontend Location:** `src/app/dashboard/client/_components/ClientTrackerPage.js`
- **Method:** `GET`
- **Endpoint:** `/api/v1/pm/projects/${projectId}/timeline`
- **Response Parsing:**
  ```javascript
  const timelineEntries = data?.timeline?.entries || [];
  // Maps to Kanban columns based on entry.status
  ```
- **Expected Column Mapping:**
  - `not_started` → "To Do"
  - `in_progress` → "In Progress"
  - `completed` → "Completed"
  - `blocked` → "Under Review"

#### 6. Generate Report
- **Frontend Location:** `src/app/dashboard/client/_components/ClientReportPage.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/pm/reports`
- **Payload Sent:**
  ```json
  {
    "project_id": "proj-uuid",
    "cadence": "weekly",
    "days_since_last_report": 7,
    "requester_notes": "Get project status report"
  }
  ```
- **⚠️ NOTE:** The frontend sends `requester_notes` (matching the user-provided API doc typo). Please ensure backend accepts this key.

---

### B. Secretary Agent Endpoints

#### 1. List Conversations
- **Frontend Location:** `src/app/_components/MessagesCard.js`
- **Method:** `GET`
- **Endpoint:** `/api/v1/secretary/projects/${projectId}/conversations`
- **Response Parsing:**
  ```javascript
  const conversations = data || [];
  // Expected fields: conversation_id, title, participants, conversation_type
  ```

#### 2. Send Message
- **Frontend Location:** `src/app/_components/MessagesCard.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/secretary/messages`
- **Payload Sent:**
  ```json
  {
    "project_id": "proj-uuid",
    "conversation_id": "conv-id",
    "sender_type": "client", 
    "sender_id": "user-email",
    "sender_name": "Client Name",
    "content": "Message text",
    "reply_to": null
  }
  ```

#### 3. Get Chat History
- **Frontend Location:** `src/app/_components/MessagesCard.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/secretary/chat/history`
- **Payload Sent:**
  ```json
  {
    "conversation_id": "conv-id",
    "limit": 50,
    "before_message_id": null
  }
  ```
- **Response Parsing:** `data.messages` (Array of message objects)

#### 4. Get Suggestions
- **Frontend Location:** `src/app/_components/MessagesCard.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/secretary/suggest`
- **Payload Sent:**
  ```json
  {
    "project_id": "proj-uuid",
    "conversation_id": "conv-id",
    "current_message": "User typed text",
    "context_messages": 10
  }
  ```
- **Response Parsing:**
  ```javascript
  response.suggestions // Array of strings
  response.tone_analysis // String
  response.reasoning // String
  ```

---

### C. Talent Acquisition Endpoints

#### 1. CV Signup
- **Frontend Location:** `src/app/register/talent/page.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/talent/signup/cv`
- **Payload Sent:**
  ```json
  {
    "user_id": "user-email-parsed",
    "email": "user@example.com",
    "full_name": "Full Name",
    "cv_text": "Pasted CV text...",
    "cv_format": "text"
  }
  ```
- **Response Parsing:** `response.profile_id` (Saved to session)

#### 2. Generate Profile
- **Frontend Location:** `src/app/register/talent/page.js`
- **Method:** `POST`
- **Endpoint:** `/api/v1/talent/profiles/${profileId}/generate`
- **Payload Sent:**
  ```json
  {
    "profile_id": "profile-uuid",
    "enhance_with_ai": true
  }
  ```

---

## 3. Data Flow Summary

1. **User creates project** → `POST /pm/projects/bootstrap` → `project_id` saved to `localStorage`.
2. **User views dashboard** → `GET /pm/projects/{id}/context` (reads ID from session).
3. **User generates tasks** → `POST /pm/task-breakdown`.
4. **User generates timeline** → `POST /pm/timeline/generate`.
5. **Kanban Board** → `GET /pm/projects/{id}/timeline`.
6. **Secretary Chat** → `GET /secretary/projects/{id}/conversations` → `POST /secretary/messages`.

---

## 4. Action Items for Backend

1. **Fix Azure Search Error:** The backend tries to connect to `keroyokan-vecdb.search.windows.net` even when running locally. Ensure local mode (`USE_MICROSOFT_AGENT_FRAMEWORK=false`) completely skips Azure AI Search initialization or handles the missing config gracefully.
2. **Payload Key:** Confirm if `requester_notes` (used by frontend) is the intended key or if it should be `requester_notes`.
3. **Response Shape:** Ensure all endpoints return the JSON structure defined in `api-usage.md` (specifically `result.snapshot` for bootstrap and `timeline.entries` for timeline).
4. **CORS:** Ensure `http://localhost:3000` is allowed if testing locally.
