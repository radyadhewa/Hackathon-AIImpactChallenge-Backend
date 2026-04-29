# Keroyok.AI API Usage Guide

This document explains how to use the backend APIs, what payloads they expect, and how the core data models are shaped.

## Base Information

- **Base URL:** `http://127.0.0.1:8000`
- **API prefix:** `/api/v1`
- **Main routers:**
  - `/api/v1/pm` - PM Agent
  - `/api/v1/secretary` - Secretary Agent
  - `/api/v1/talent` - Talent Acquisition Agent
- **Runtime note:** If Azure settings are missing, the backend falls back to deterministic local behavior.
- **Auth:** Not implemented yet.

## Configuration

The app reads settings from `.env` or environment variables.

| Variable | Purpose |
|---|---|
| `APP_NAME` | Display name of the backend |
| `APP_ENV` | Environment label (`local`, `dev`, etc.) |
| `API_V1_PREFIX` | API prefix, default `/api/v1` |
| `CONTEXT_BANK_DIR` | Local JSON storage for project memory |
| `USE_MICROSOFT_AGENT_FRAMEWORK` | Enables Azure runtime when configured |
| `AZURE_FOUNDRY_ENDPOINT` | Azure AI Foundry resource endpoint |
| `AZURE_FOUNDRY_API_KEY` | Azure AI Foundry API key |
| `AZURE_FOUNDRY_CHAT_DEPLOYMENT` | Chat deployment name |
| `AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT` | Embedding deployment name |
| `AZURE_AI_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_AI_SEARCH_API_KEY` | Azure AI Search key |
| `AZURE_AI_SEARCH_INDEX_NAME` | Search index name |
| `AZURE_AI_SEARCH_VECTOR_DIMENSIONS` | Vector size, default `1536` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB endpoint |
| `COSMOS_KEY` | Azure Cosmos DB key |
| `COSMOS_DATABASE` | Cosmos DB database name |
| `COSMOS_CONTEXT_CONTAINER` | Cosmos DB container name for the context bank |
| `COSMOS_CHAT_CONTAINER` | Cosmos DB container name for chat and meeting data |
| `COSMOS_PROFILE_CONTAINER` | Optional Cosmos container for freelancer profiles and match data; leave blank for local JSON |
| `COSMOS_PM_LOG_CONTAINER` | Optional Cosmos container for PM logs; leave blank for local JSON |

---

## Response Shape Conventions

Most endpoints return one of these patterns:

- a single resource, for example `ProfileResponse` or `ConversationResponse`
- a resource plus a stored context record, for example `TaskBreakdownResponse`
- a list of resources, for example `ProjectEventsResponse`
- a result object plus a context record, for example `ChatSummarizeResponse`

All dates/times are ISO-8601 strings in API JSON.

---

# 1) PM Agent API

## 1.1 Health

### `GET /api/v1/pm/health`
Returns runtime and storage backend status.

**Response model:** `HealthResponse`

```json
{
  "status": "ok",
  "runtime": "local-template-runtime",
  "context_bank": "local-json-only"
}
```

---

## 1.2 Bootstrap Project Context

### `POST /api/v1/pm/projects/bootstrap`
Creates the project context file and initial snapshot.

**Request model:** `ProjectBootstrapRequest`

### Payload
```json
{
  "overview": {
    "project_id": "proj-demo",
    "project_name": "Enterprise Website Revamp",
    "client_name": "Acme Corp",
    "description": "Build a multilingual B2B marketing site.",
    "scope": "Discovery, design QA, frontend build, CMS handoff.",
    "success_criteria": ["Launch in 6 weeks", "Mobile responsive", "CMS editable"],
    "constraints": ["Budget capped", "Async collaboration only"],
    "freelancers": [
      {
        "name": "Dina",
        "role": "Frontend Engineer",
        "hours_per_week": 20,
        "timezone": "Asia/Jakarta",
        "skills": ["Next.js", "Tailwind"]
      }
    ],
    "milestones": [
      {
        "name": "Design freeze",
        "due_date": "2026-05-15",
        "success_definition": "Approved UI kit"
      }
    ],
    "timeline_notes": "Client wants weekly updates"
  }
}
```

### Response model: `ProjectContextResponse`

```json
{
  "snapshot": {
    "project_id": "proj-demo",
    "overview": {
      "project_id": "proj-demo",
      "project_name": "Enterprise Website Revamp",
      "client_name": "Acme Corp",
      "description": "Build a multilingual B2B marketing site.",
      "scope": "Discovery, design QA, frontend build, CMS handoff.",
      "success_criteria": ["Launch in 6 weeks"],
      "constraints": ["Budget capped"],
      "freelancers": [],
      "milestones": [],
      "timeline_notes": "Client wants weekly updates"
    },
    "recent_entries": []
  }
}
```

---

## 1.3 PM Logs

### `GET /api/v1/pm/projects/{project_id}/logs`
Retrieve PM agent logs from Cosmos DB.

**Query params:**
- `action_type` (optional) – filter by action type (e.g., `report`, `work_check`)
- `limit` (optional) – max results (default 50)
- `offset` (optional) – skip the first N results (default 0)

**Response model:** `PmLogListResponse`

```json
{
  "logs": [
    {
      "log_id": "proj-1:report:2026-04-28T10:00:00Z",
      "project_id": "proj-1",
      "action_type": "report",
      "summary": "Project is moving with early planning momentum.",
      "payload": {"cadence": "weekly", "overall_status": "watch"},
      "actor": "reporter_subagent",
      "metadata": {},
      "created_at": "2026-04-28T10:00:00Z"
    }
  ]
}
```

## 1.3 Add Project Update

### `POST /api/v1/pm/projects/{project_id}/updates`
Stores a project update as a context-bank record.

**Request model:** `ProjectUpdateRequest`

### Payload
```json
{
  "title": "Kickoff completed",
  "content": "Client confirmed MVP scope and launch urgency.",
  "tags": ["kickoff"],
  "source": "client-chat",
  "metadata": {
    "channel": "whatsapp"
  }
}
```

### Response model: `ContextRecordResponse`

```json
{
  "record": {
    "id": "uuid",
    "project_id": "proj-demo",
    "entry_type": "project_update",
    "title": "Kickoff completed",
    "content": "Client confirmed MVP scope and launch urgency.",
    "tags": ["kickoff"],
    "metadata": {
      "channel": "whatsapp"
    },
    "source": "client-chat",
    "created_at": "2026-04-27T00:00:00Z"
  }
}
```

---

## 1.4 Get Project Context

### `GET /api/v1/pm/projects/{project_id}/context`
Returns the project overview plus the latest context records.

**Response model:** `ProjectContextResponse`

### Response
```json
{
  "snapshot": {
    "project_id": "proj-demo",
    "overview": { "...": "..." },
    "recent_entries": [
      {
        "id": "uuid",
        "entry_type": "project_update",
        "title": "Kickoff completed",
        "content": "Client confirmed MVP scope..."
      }
    ]
  }
}
```

---

## 1.5 Task Breakdown

### `POST /api/v1/pm/task-breakdown`
Creates a task breakdown from project goals and source material.

**Request model:** `TaskBreakdownRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "delivery_goal": "Launch MVP website",
  "source_material": "Client wants polished enterprise feel, CMS editing, and responsive pages for product + case studies.",
  "freelancer_focus": ["Frontend Engineer", "Designer"]
}
```

### Response model: `TaskBreakdownResponse`

```json
{
  "result": {
    "summary": "Break the work into execution-ready streams.",
    "assumptions": ["Scope is stable for one sprint"],
    "tasks": [
      {
        "task_id": "TASK-1",
        "title": "Create landing page shell",
        "description": "Build the responsive shell for the landing page.",
        "assigned_to": "Dina",
        "estimated_hours": 10,
        "priority": "high",
        "due_hint": "This week",
        "dependencies": [],
        "acceptance_criteria": ["Responsive on mobile and desktop"],
        "recommended_references": ["Client brief"]
      }
    ]
  },
  "context_record": {
    "id": "uuid",
    "entry_type": "task_breakdown",
    "title": "Task breakdown for Launch MVP website"
  }
}
```

---

## 1.6 Work Check

### `POST /api/v1/pm/work-check`
Checks submitted work against scope and returns feedback.

**Request model:** `WorkCheckRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "task_id": "TASK-1",
  "task_title": "Create landing page shell",
  "freelancer_name": "Dina",
  "scope_reference": "Responsive landing page plus CMS handoff notes.",
  "deliverable_summary": "Responsive page shell complete.",
  "deliverable_artifact": "Responsive landing page shell is done but CMS handoff notes are missing.",
  "requester_notes": "Please keep the review direct."
}
```

### Response model: `WorkCheckResponse`

```json
{
  "result": {
    "verdict": "revise",
    "scope_alignment_score": 68,
    "summary": "Good start, but the artifact needs tighter mapping to scope.",
    "strengths": ["Structure is clear."],
    "gaps": ["Missing explicit CMS handoff notes."],
    "improvement_actions": ["Add CMS handoff section."],
    "reference_suggestions": ["Review the scope reference again."],
    "needs_escalation": false,
    "escalation_message": null
  },
  "context_record": {
    "entry_type": "work_check"
  }
}
```

---

## 1.7 Reports

### `POST /api/v1/pm/reports`
Generates a weekly or ad hoc project report.

**Request model:** `ReportRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "cadence": "weekly",
  "days_since_last_report": 7,
  "requester_notes": "Summarize risks and morale."
}
```

### Response model: `ReportResponse`

```json
{
  "result": {
    "summary": "Project is moving with early planning momentum.",
    "progress_percent": 35,
    "overall_status": "watch",
    "wins": ["Task plan is created."],
    "blockers": [],
    "upcoming_actions": ["Review first frontend deliverable."],
    "risks": ["Need more project updates from freelancers."],
    "escalations": [],
    "morale_coaching": ["Keep documenting async decisions."]
  },
  "context_record": {
    "entry_type": "report"
  }
}
```

---

## 1.8 Timeline Generation

### `POST /api/v1/pm/timeline/generate`
Generates a schedule from the latest task breakdown.

**Request model:** `TimelineGenerateRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "start_date": "2026-04-28T09:00:00Z"
}
```

### Response model: `TimelineResponse`

```json
{
  "timeline": {
    "project_id": "proj-demo",
    "entries": [
      {
        "entry_id": "TASK-1",
        "project_id": "proj-demo",
        "entry_type": "task",
        "title": "Create landing page shell",
        "description": "Build the responsive shell for the landing page.",
        "start_date": "2026-04-28T09:00:00Z",
        "due_date": "2026-05-05T09:00:00Z",
        "assigned_to": "Dina",
        "dependencies": [],
        "status": "not_started",
        "estimated_hours": 10,
        "actual_hours": null,
        "created_at": "2026-04-27T00:00:00Z",
        "updated_at": "2026-04-27T00:00:00Z"
      }
    ],
    "critical_path": ["TASK-1"],
    "generated_at": "2026-04-27T00:00:00Z"
  },
  "context_record": {
    "entry_type": "timeline"
  }
}
```

---

## 1.9 Get Timeline

### `GET /api/v1/pm/projects/{project_id}/timeline`
Returns the stored/generated project timeline.

**Response model:** `TimelineResponse`

```json
{
  "timeline": {
    "project_id": "proj-demo",
    "entries": [],
    "critical_path": [],
    "generated_at": "2026-04-27T00:00:00Z"
  },
  "context_record": null
}
```

---

## 1.10 Update Task Status

### `POST /api/v1/pm/projects/{project_id}/tasks/{task_id}/status`
Updates a timeline entry status and records it in context.

**Request model:** `TaskStatusUpdateRequest`

### Payload
```json
{
  "status": "completed",
  "actual_hours": 10,
  "notes": "Completed and reviewed."
}
```

### Response model: `ContextRecordResponse`

```json
{
  "record": {
    "entry_type": "task_status_update",
    "title": "Task TASK-1 status updated to completed"
  }
}
```

---

## 1.11 Get Agent Events

### `GET /api/v1/pm/projects/{project_id}/events?target_agent=pm_agent`
Returns unresolved or filtered agent events.

**Response model:** `ProjectEventsResponse`

```json
{
  "events": [
    {
      "event_id": "uuid",
      "project_id": "proj-demo",
      "source_agent": "secretary_agent",
      "event_type": "task_created",
      "title": "Action item from chat: Create wireframes",
      "description": "Create wireframes for landing page",
      "target_agent": "pm_agent",
      "metadata": {
        "conversation_id": "conv-123",
        "priority": "high"
      },
      "created_at": "2026-04-27T00:00:00Z",
      "resolved": false,
      "resolved_at": null,
      "resolved_by": null
    }
  ]
}
```

---

## 1.12 Resolve Agent Event

### `POST /api/v1/pm/projects/{project_id}/events/{event_id}/resolve`
Marks an event as handled.

**Request model:** `ResolveEventRequest`

### Payload
```json
{
  "resolved_by": "human_pm"
}
```

### Response
```json
{
  "status": "resolved",
  "event_id": "uuid"
}
```

---

# 2) Secretary Agent API

## 2.1 Create Conversation

### `POST /api/v1/secretary/conversations`
Creates a new conversation channel.

**Request model:** `ConversationCreateRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "conversation_type": "project_channel",
  "title": "Sprint Planning",
  "participants": ["Dina", "Rafi"]
}
```

### Response model: `ConversationResponse`

```json
{
  "conversation": {
    "conversation_id": "uuid",
    "project_id": "proj-demo",
    "conversation_type": "project_channel",
    "title": "Sprint Planning",
    "participants": ["Dina", "Rafi"],
    "created_at": "2026-04-27T00:00:00Z",
    "last_message_at": null,
    "is_active": true
  }
}
```

---

## 2.2 List Conversations

### `GET /api/v1/secretary/projects/{project_id}/conversations`
Lists all conversations for a project.

**Response:** array of `Conversation`

```json
[
  {
    "conversation_id": "uuid",
    "project_id": "proj-demo",
    "conversation_type": "project_channel",
    "title": "Sprint Planning",
    "participants": ["Dina", "Rafi"],
    "created_at": "2026-04-27T00:00:00Z",
    "last_message_at": null,
    "is_active": true
  }
]
```

---

## 2.3 Send Message

### `POST /api/v1/secretary/messages`
Saves a message in a conversation.

**Request model:** `MessageSendRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "conversation_id": "uuid",
  "sender_type": "freelancer",
  "sender_id": "user-dina",
  "sender_name": "Dina",
  "content": "Hi team! When should we start the frontend work?",
  "reply_to": null
}
```

### Response model: `MessageResponse`

```json
{
  "message": {
    "message_id": "uuid",
    "conversation_id": "uuid",
    "project_id": "proj-demo",
    "sender_type": "freelancer",
    "sender_id": "user-dina",
    "sender_name": "Dina",
    "content": "Hi team! When should we start the frontend work?",
    "reply_to": null,
    "timestamp": "2026-04-27T00:00:00Z",
    "edited_at": null,
    "metadata": {}
  }
}
```

---

## 2.4 Chat History

### `POST /api/v1/secretary/chat/history`
Fetches conversation messages.

**Request model:** `ChatHistoryRequest`

### Payload
```json
{
  "conversation_id": "uuid",
  "limit": 50,
  "before_message_id": null
}
```

### Response model: `ChatHistoryResponse`

```json
{
  "messages": [
    {
      "message_id": "uuid",
      "content": "Hi team! When should we start the frontend work?"
    }
  ],
  "has_more": false
}
```

---

## 2.5 Summarize Chat

### `POST /api/v1/secretary/chat/summarize`
Summarizes a thread and can create PM events from action items.

**Request model:** `ChatSummarizeRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "conversation_id": "uuid",
  "message_count": 50,
  "create_action_items": true
}
```

### Response model: `ChatSummarizeResponse`

```json
{
  "summary": {
    "summary_id": "uuid",
    "conversation_id": "uuid",
    "project_id": "proj-demo",
    "summary": "Discussed project timeline and assigned tasks.",
    "key_points": ["Timeline is tight", "Need more resources"],
    "decisions_made": ["Use Next.js for frontend"],
    "action_items": [
      {
        "item_id": "uuid",
        "project_id": "proj-demo",
        "conversation_id": "uuid",
        "content": "Create wireframes for landing page",
        "assignee": "Rafi",
        "priority": "high",
        "source_type": "chat",
        "status": "pending"
      }
    ],
    "participants": ["Dina", "Rafi"],
    "message_count": 2,
    "from_timestamp": "2026-04-27T00:00:00Z",
    "to_timestamp": "2026-04-27T00:05:00Z",
    "created_at": "2026-04-27T00:06:00Z"
  },
  "context_record": {
    "entry_type": "chat_summary"
  },
  "events_created": [
    {
      "event_type": "task_created",
      "target_agent": "pm_agent"
    }
  ]
}
```

---

## 2.6 Create Meeting

### `POST /api/v1/secretary/meetings`
Schedules a meeting.

**Request model:** `MeetingCreateRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "title": "Sprint Kickoff",
  "scheduled_at": "2026-05-01T10:00:00Z",
  "duration_minutes": 60,
  "participants": ["Dina", "Rafi"]
}
```

### Response model: `MeetingResponse`

```json
{
  "meeting": {
    "meeting_id": "uuid",
    "project_id": "proj-demo",
    "title": "Sprint Kickoff",
    "scheduled_at": "2026-05-01T10:00:00Z",
    "duration_minutes": 60,
    "participants": ["Dina", "Rafi"],
    "status": "scheduled",
    "recording_url": null,
    "transcript": null,
    "created_at": "2026-04-27T00:00:00Z",
    "completed_at": null
  }
}
```

---

## 2.7 List Meetings

### `GET /api/v1/secretary/projects/{project_id}/meetings?status=completed`
Lists meetings. `status` is optional.

**Response:** array of `Meeting`

---

## 2.8 Complete Meeting and Generate MoM

### `POST /api/v1/secretary/projects/{project_id}/meetings/{meeting_id}/complete`
Stores transcript, marks the meeting complete, and generates minutes of meeting.

**Request model:** `MeetingCompleteRequest`

### Payload
```json
{
  "transcript": "Dina: Welcome everyone...",
  "absentees": []
}
```

### Response model: `MeetingCompleteResponse`

```json
{
  "meeting": {
    "meeting_id": "uuid",
    "status": "completed",
    "transcript": "Dina: Welcome everyone...",
    "completed_at": "2026-04-27T00:30:00Z"
  },
  "mom": {
    "mom_id": "uuid",
    "meeting_id": "uuid",
    "project_id": "proj-demo",
    "meeting_title": "Sprint Kickoff",
    "conducted_at": "2026-04-27T00:30:00Z",
    "participants": ["Dina", "Rafi"],
    "absentees": [],
    "agenda": ["Project kickoff", "Timeline review"],
    "key_discussions": ["timeline: reviewed 6-week plan"],
    "decisions_made": ["Use Next.js for frontend"],
    "action_items": [
      {
        "item_id": "uuid",
        "project_id": "proj-demo",
        "meeting_id": "uuid",
        "content": "Create wireframes for all pages",
        "assignee": "Rafi",
        "priority": "high",
        "source_type": "meeting",
        "status": "pending"
      }
    ],
    "next_meeting": {
      "suggested_date": "2026-05-05",
      "agenda_preview": ["Review wireframes", "Discuss architecture"]
    },
    "created_at": "2026-04-27T00:35:00Z"
  },
  "context_record": {
    "entry_type": "meeting_minutes"
  },
  "events_created": [
    {
      "event_type": "task_created",
      "target_agent": "pm_agent"
    }
  ]
}
```

---

## 2.9 Secretary Suggestions

### `POST /api/v1/secretary/suggest`
Returns suggested response drafts for the current message.

**Request model:** `SecretarySuggestRequest`

### Payload
```json
{
  "project_id": "proj-demo",
  "conversation_id": "uuid",
  "current_message": "Sure, I will",
  "context_messages": 10
}
```

### Response model: `SecretarySuggestResponse`

```json
{
  "suggestions": [
    "Thanks for the update! I'll review the timeline and get back to you by EOD.",
    "Got it, let me check my schedule and confirm.",
    "Noted. Will follow up soon."
  ],
  "reasoning": "The conversation is professional and requires a commitment to follow up.",
  "tone_analysis": "Professional, collaborative, slightly urgent"
}
```

---

# 3) Talent Acquisition Agent API

## 3.1 CV Sign-up / Parse

### `POST /api/v1/talent/signup/cv`
Parses CV text and creates a freelancer profile.

**Request model:** `CVUploadRequest`

### Payload
```json
{
  "user_id": "user-123",
  "email": "john@example.com",
  "full_name": "John Doe",
  "cv_text": "Paste CV text here...",
  "cv_format": "text"
}
```

### Response model: `CVParseResponse`

```json
{
  "profile_id": "uuid",
  "raw_extracted_data": {
    "location": "Jakarta, Indonesia",
    "timezone": "Asia/Jakarta",
    "languages": ["Indonesian", "English"],
    "hourly_rate": 25,
    "availability_hours_per_week": 30,
    "skills": [
      {
        "name": "React",
        "category": "Frontend",
        "proficiency": "expert",
        "years_experience": 5
      }
    ],
    "experiences": [
      {
        "company": "TechCorp Indonesia",
        "role": "Senior Frontend Developer",
        "start_date": "2021-01-01",
        "end_date": null,
        "is_current": true,
        "description": "Leading frontend development for e-commerce platform",
        "skills_used": ["React", "TypeScript"]
      }
    ],
    "portfolio": []
  },
  "parsed_profile": {
    "profile_id": "uuid",
    "user_id": "user-123",
    "email": "john@example.com",
    "full_name": "John Doe",
    "skills": [
      {
        "name": "React",
        "category": "Frontend",
        "proficiency": "expert"
      }
    ],
    "is_available": true
  },
  "context_record": {
    "entry_type": "cv_parsed"
  }
}
```

---

## 3.2 Generate Enhanced Profile

### `POST /api/v1/talent/profiles/{profile_id}/generate`
Creates AI-generated headline, bio, and profile summary.

**Request model:** `ProfileGenerateRequest`

### Payload
```json
{
  "profile_id": "uuid",
  "enhance_with_ai": true
}
```

### Response model: `ProfileGenerateResponse`

```json
{
  "profile": {
    "profile_id": "uuid",
    "headline": "Expert React Developer | 5+ Years Building Scalable Web Apps",
    "bio": "Passionate frontend developer...",
    "profile_summary": "React expert specializing in scalable web applications...",
    "top_skills_summary": "React, TypeScript, Node.js, Redux, Frontend Architecture"
  },
  "generated_summary": "React expert specializing in scalable web applications...",
  "generated_headline": "Expert React Developer | 5+ Years Building Scalable Web Apps",
  "top_skills_highlight": [
    "React: Expert-level with 5 years building production apps",
    "TypeScript: Strong typing and architecture skills"
  ],
  "context_record": {
    "entry_type": "profile_enhanced"
  }
}
```

---

## 3.3 Get Profile

### `GET /api/v1/talent/profiles/{profile_id}`
Returns a freelancer profile.

**Response model:** `ProfileResponse`

```json
{
  "profile": {
    "profile_id": "uuid",
    "user_id": "user-123",
    "email": "john@example.com",
    "full_name": "John Doe",
    "headline": "Expert React Developer",
    "bio": "...",
    "location": "Jakarta, Indonesia",
    "timezone": "Asia/Jakarta",
    "languages": ["Indonesian", "English"],
    "hourly_rate": 25,
    "availability_hours_per_week": 30,
    "skills": [],
    "experiences": [],
    "portfolio": [],
    "profile_embedding": null,
    "profile_summary": null,
    "top_skills_summary": null,
    "match_score": null,
    "is_available": true,
    "created_at": "2026-04-27T00:00:00Z",
    "updated_at": "2026-04-27T00:00:00Z"
  }
}
```

---

## 3.4 Get Profile by User

### `GET /api/v1/talent/users/{user_id}/profile`
Finds a profile by `user_id`.

**Response model:** `ProfileResponse`

---

## 3.5 Update Profile

### `PATCH /api/v1/talent/profiles/{profile_id}`
Updates selected profile fields.

**Request model:** `ProfileUpdateRequest`

### Payload
```json
{
  "headline": "Updated Headline",
  "bio": "Updated bio",
  "hourly_rate": 50,
  "availability_hours_per_week": 25,
  "is_available": true
}
```

### Response model: `ProfileResponse`

---

## 3.6 Search Profiles

### `POST /api/v1/talent/profiles/search`
Searches profiles by skills and filters.

**Request model:** `ProfileSearchRequest`

### Payload
```json
{
  "skills": ["React", "TypeScript"],
  "min_hourly_rate": 20,
  "max_hourly_rate": 50,
  "available_only": true,
  "limit": 20
}
```

### Response model: `ProfileSearchResponse`

```json
{
  "profiles": [
    {
      "profile_id": "uuid",
      "full_name": "John Doe",
      "skills": [{ "name": "React" }],
      "is_available": true
    }
  ],
  "total_count": 1
}
```

---

## 3.7 Create Match Request and Find Matches

### `POST /api/v1/talent/match`
Creates a match request and returns ranked freelancer matches.

**Request model:** `MatchCreateRequest`

### Payload
```json
{
  "project_id": "proj-match",
  "project_description": "Need a React developer to build an e-commerce frontend",
  "required_skills": ["React", "TypeScript"],
  "budget_min": 20,
  "budget_max": 50,
  "timeline_weeks": 8,
  "top_k": 5
}
```

### Response model: `MatchCreateResponse`

```json
{
  "request_id": "uuid",
  "matches": [
    {
      "match_id": "uuid",
      "request_id": "uuid",
      "profile_id": "uuid",
      "match_score": 0.92,
      "match_reasoning": "Strong match based on skills: React, TypeScript. Has 2 relevant experiences. Rate fits within budget range.",
      "skill_match_percentage": 100,
      "experience_relevance_score": 0.92,
      "availability_match": true,
      "created_at": "2026-04-27T00:00:00Z"
    }
  ],
  "context_record": {
    "entry_type": "match_request"
  }
}
```

---

## 3.8 Get Match Details

### `GET /api/v1/talent/matches/{match_id}`
Returns match details plus the profile that was matched.

**Response model:** `MatchResultResponse`

```json
{
  "match_id": "uuid",
  "profile": {
    "profile_id": "uuid",
    "full_name": "John Doe"
  },
  "match_score": 0.92,
  "match_reasoning": "Strong match based on skills...",
  "skill_match_percentage": 100
}
```

---

# 4) Core Data Models

## 4.1 Project and PM Models

### `ProjectOverview`
Used to bootstrap the shared project memory.

| Field | Type |
|---|---|
| `project_id` | string |
| `project_name` | string |
| `client_name` | string or null |
| `description` | string |
| `scope` | string |
| `success_criteria` | string[] |
| `constraints` | string[] |
| `freelancers` | `FreelancerAvailability[]` |
| `milestones` | `Milestone[]` |
| `timeline_notes` | string or null |

### `FreelancerAvailability`
| Field | Type |
|---|---|
| `name` | string |
| `role` | string |
| `hours_per_week` | int |
| `timezone` | string |
| `skills` | string[] |
| `notes` | string or null |

### `TaskItem`
| Field | Type |
|---|---|
| `task_id` | string |
| `title` | string |
| `description` | string |
| `assigned_to` | string |
| `estimated_hours` | int |
| `priority` | string |
| `due_hint` | string |
| `dependencies` | string[] |
| `acceptance_criteria` | string[] |
| `recommended_references` | string[] |

### `TaskBreakdownResult`
| Field | Type |
|---|---|
| `summary` | string |
| `assumptions` | string[] |
| `tasks` | `TaskItem[]` |

### `WorkCheckResult`
| Field | Type |
|---|---|
| `verdict` | string |
| `scope_alignment_score` | int (0-100) |
| `summary` | string |
| `strengths` | string[] |
| `gaps` | string[] |
| `improvement_actions` | string[] |
| `reference_suggestions` | string[] |
| `needs_escalation` | bool |
| `escalation_message` | string or null |

### `ProjectReport`
| Field | Type |
|---|---|
| `summary` | string |
| `progress_percent` | int (0-100) |
| `overall_status` | `on_track | watch | at_risk` |
| `wins` | string[] |
| `blockers` | string[] |
| `upcoming_actions` | string[] |
| `risks` | string[] |
| `escalations` | string[] |
| `morale_coaching` | string[] |

---

## 4.2 Timeline and Events

### `TimelineEntry`
| Field | Type |
|---|---|
| `entry_id` | string |
| `project_id` | string |
| `entry_type` | `milestone | task | deadline` |
| `title` | string |
| `description` | string |
| `start_date` | datetime or null |
| `due_date` | datetime or null |
| `assigned_to` | string or null |
| `dependencies` | string[] |
| `status` | `not_started | in_progress | completed | blocked` |
| `estimated_hours` | int |
| `actual_hours` | int or null |
| `created_at` | datetime |
| `updated_at` | datetime |

### `ProjectTimeline`
| Field | Type |
|---|---|
| `project_id` | string |
| `entries` | `TimelineEntry[]` |
| `critical_path` | string[] |
| `generated_at` | datetime |

### `AgentEvent`
| Field | Type |
|---|---|
| `event_id` | string |
| `project_id` | string |
| `source_agent` | string |
| `event_type` | `escalation | task_created | task_completed | help_needed | timeline_update` |
| `title` | string |
| `description` | string |
| `target_agent` | string or null |
| `metadata` | object |
| `created_at` | datetime |
| `resolved` | bool |
| `resolved_at` | datetime or null |
| `resolved_by` | string or null |

---

## 4.3 Secretary and Communication Models

### `Message`
| Field | Type |
|---|---|
| `message_id` | string |
| `conversation_id` | string |
| `project_id` | string |
| `sender_type` | `freelancer | client | agent | system` |
| `sender_id` | string |
| `sender_name` | string |
| `content` | string |
| `reply_to` | string or null |
| `timestamp` | datetime |
| `edited_at` | datetime or null |
| `metadata` | object |

### `Conversation`
| Field | Type |
|---|---|
| `conversation_id` | string |
| `project_id` | string |
| `conversation_type` | `direct | group | project_channel` |
| `title` | string or null |
| `participants` | string[] |
| `created_at` | datetime |
| `last_message_at` | datetime or null |
| `is_active` | bool |

### `Meeting`
| Field | Type |
|---|---|
| `meeting_id` | string |
| `project_id` | string |
| `title` | string |
| `scheduled_at` | datetime |
| `duration_minutes` | int |
| `participants` | string[] |
| `status` | `scheduled | ongoing | completed | cancelled` |
| `recording_url` | string or null |
| `transcript` | string or null |
| `created_at` | datetime |
| `completed_at` | datetime or null |

### `ActionItem`
| Field | Type |
|---|---|
| `item_id` | string |
| `meeting_id` | string or null |
| `conversation_id` | string or null |
| `project_id` | string |
| `content` | string |
| `assignee` | string or null |
| `due_date` | datetime or null |
| `status` | `pending | in_progress | completed` |
| `priority` | `high | medium | low` |
| `source_type` | `meeting | chat` |
| `created_at` | datetime |
| `completed_at` | datetime or null |

### `ChatSummary`
| Field | Type |
|---|---|
| `summary_id` | string |
| `conversation_id` | string |
| `project_id` | string |
| `summary` | string |
| `key_points` | string[] |
| `decisions_made` | string[] |
| `action_items` | `ActionItem[]` |
| `participants` | string[] |
| `message_count` | int |
| `from_timestamp` | datetime |
| `to_timestamp` | datetime |
| `created_at` | datetime |

### `MinutesOfMeeting`
| Field | Type |
|---|---|
| `mom_id` | string |
| `meeting_id` | string |
| `project_id` | string |
| `meeting_title` | string |
| `conducted_at` | datetime |
| `participants` | string[] |
| `absentees` | string[] |
| `agenda` | string[] |
| `key_discussions` | string[] |
| `decisions_made` | string[] |
| `action_items` | `ActionItem[]` |
| `next_meeting` | object or null |
| `created_at` | datetime |

---

## 4.4 Talent Models

### `Skill`
| Field | Type |
|---|---|
| `name` | string |
| `category` | string or null |
| `proficiency` | `beginner | intermediate | advanced | expert` |
| `years_experience` | float or null |
| `verified` | bool |

### `Experience`
| Field | Type |
|---|---|
| `experience_id` | string |
| `company` | string or null |
| `role` | string |
| `start_date` | date or null |
| `end_date` | date or null |
| `is_current` | bool |
| `description` | string or null |
| `skills_used` | string[] |

### `PortfolioItem`
| Field | Type |
|---|---|
| `item_id` | string |
| `title` | string |
| `description` | string or null |
| `project_url` | string or null |
| `thumbnail_url` | string or null |
| `skills_demonstrated` | string[] |
| `completion_date` | date or null |

### `FreelancerProfile`
| Field | Type |
|---|---|
| `profile_id` | string |
| `user_id` | string |
| `email` | string |
| `full_name` | string |
| `headline` | string or null |
| `bio` | string or null |
| `location` | string or null |
| `timezone` | string or null |
| `languages` | string[] |
| `hourly_rate` | float or null |
| `availability_hours_per_week` | int or null |
| `skills` | `Skill[]` |
| `experiences` | `Experience[]` |
| `portfolio` | `PortfolioItem[]` |
| `profile_embedding` | float[] or null |
| `profile_summary` | string or null |
| `top_skills_summary` | string or null |
| `match_score` | float or null |
| `is_available` | bool |
| `created_at` | datetime |
| `updated_at` | datetime |

### `MatchRequest`
| Field | Type |
|---|---|
| `request_id` | string |
| `project_id` | string or null |
| `project_description` | string |
| `required_skills` | string[] |
| `budget_range` | object or null |
| `timeline_weeks` | int or null |
| `request_embedding` | float[] or null |
| `created_at` | datetime |

### `MatchResult`
| Field | Type |
|---|---|
| `match_id` | string |
| `request_id` | string |
| `profile_id` | string |
| `match_score` | float |
| `match_reasoning` | string |
| `skill_match_percentage` | float |
| `experience_relevance_score` | float |
| `availability_match` | bool |
| `created_at` | datetime |

---

# 5) Storage and Data Flow

## Local storage layout

The backend persists data under `CONTEXT_BANK_DIR`:

```text
context_bank/
  {project_id}/
    project.json
    records/
      {context-record-id}.json
      timeline_{entry_id}.json
      event_{event_id}.json
      msg_{conversation_id}_{message_id}.json
      conv_{conversation_id}.json
      meeting_{meeting_id}.json
  profiles/
    {profile_id}.json
  matches/
    {match_id}.json
```

## Main flow patterns

### PM Agent
1. Bootstraps project overview
2. Writes task breakdown to context bank
3. Generates timeline from tasks
4. Records updates, events, reports

### Secretary Agent
1. Stores conversations and meetings
2. Summarizes chat or transcript
3. Converts action items into PM events

### Talent Agent
1. Parses CV text into structured profile
2. Generates embedding for profile text
3. Matches project descriptions against profile embeddings

---

# 6) Example End-to-End Flows

## Flow A: Project kickoff
1. `POST /api/v1/pm/projects/bootstrap`
2. `POST /api/v1/pm/task-breakdown`
3. `POST /api/v1/pm/timeline/generate`

## Flow B: Chat turns into tasks
1. `POST /api/v1/secretary/messages`
2. `POST /api/v1/secretary/chat/summarize`
3. Secretary creates `task_created` events
4. PM reads events from `GET /api/v1/pm/projects/{project_id}/events`

## Flow C: Meeting turns into MoM and tasks
1. `POST /api/v1/secretary/meetings`
2. `POST /api/v1/secretary/projects/{project_id}/meetings/{meeting_id}/complete`
3. MoM creates action items
4. PM resolves events into project tasks

## Flow D: Freelancer onboarding and matching
1. `POST /api/v1/talent/signup/cv`
2. `POST /api/v1/talent/profiles/{profile_id}/generate`
3. `POST /api/v1/talent/match`

---

# 7) Error Handling Notes

Common error patterns:

- `404 Not Found` when project, profile, meeting, or conversation does not exist
- `409 Conflict` when the same user tries to create a duplicate profile
- `400 Bad Request` for malformed dates or invalid requests
- `502 Bad Gateway` when a runtime does not return valid JSON

---

# 8) Recommended Client Usage

For frontend or external clients:

1. Call `bootstrap` first for any project
2. Treat `context_record` responses as your audit trail
3. Use `events` endpoints to connect Secretary and PM workflows
4. Use `match` after onboarding freelancers to shortlist candidates
5. Use timeline endpoints to render project schedules in UI

---

# 9) Quick Reference Table

| Area | Key Endpoints |
|---|---|
| PM | `/pm/health`, `/pm/projects/bootstrap`, `/pm/task-breakdown`, `/pm/work-check`, `/pm/reports`, `/pm/timeline/generate`, `/pm/projects/{id}/events` |
| Secretary | `/secretary/conversations`, `/secretary/messages`, `/secretary/chat/summarize`, `/secretary/meetings`, `/secretary/projects/{project_id}/meetings/{meeting_id}/complete`, `/secretary/suggest` |
| Talent | `/talent/signup/cv`, `/talent/profiles/{id}/generate`, `/talent/profiles/search`, `/talent/match`, `/talent/matches/{match_id}` |

---

If you want, I can also turn this into a more formal **OpenAPI-style reference** or split it into three separate docs: `pm-api.md`, `secretary-api.md`, and `talent-api.md`.
