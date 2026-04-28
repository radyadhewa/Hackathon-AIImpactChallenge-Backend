from pydantic import BaseModel, Field

from app.models.domain import (
    ActionItem,
    AgentEvent,
    ChatSummary,
    ContextBankRecord,
    Conversation,
    FreelancerProfile,
    MatchRequest,
    MatchResult,
    Meeting,
    Message,
    MinutesOfMeeting,
    ProjectContextSnapshot,
    ProjectOverview,
    ProjectReport,
    ProjectTimeline,
    TaskBreakdownResult,
    WorkCheckResult,
)


class HealthResponse(BaseModel):
    status: str
    runtime: str
    context_bank: str
    log_store: str | None = None


class ProjectBootstrapRequest(BaseModel):
    overview: ProjectOverview


class ProjectUpdateRequest(BaseModel):
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ProjectContextResponse(BaseModel):
    snapshot: ProjectContextSnapshot


class ContextRecordResponse(BaseModel):
    record: ContextBankRecord


class TaskBreakdownRequest(BaseModel):
    project_id: str
    delivery_goal: str
    source_material: str
    freelancer_focus: list[str] = Field(default_factory=list)


class TaskBreakdownResponse(BaseModel):
    result: TaskBreakdownResult
    context_record: ContextBankRecord


class WorkCheckRequest(BaseModel):
    project_id: str
    task_id: str
    task_title: str
    freelancer_name: str
    scope_reference: str
    deliverable_summary: str
    deliverable_artifact: str
    requester_notes: str | None = None


class WorkCheckResponse(BaseModel):
    result: WorkCheckResult
    context_record: ContextBankRecord


class ReportRequest(BaseModel):
    project_id: str
    cadence: str = "weekly"
    days_since_last_report: int | None = Field(default=None, ge=1)
    requester_notes: str | None = None


class ReportResponse(BaseModel):
    result: ProjectReport
    context_record: ContextBankRecord


class TimelineGenerateRequest(BaseModel):
    project_id: str
    start_date: str | None = None


class TimelineResponse(BaseModel):
    timeline: ProjectTimeline
    context_record: ContextBankRecord | None = None


class TaskStatusUpdateRequest(BaseModel):
    status: str
    actual_hours: int | None = None
    notes: str | None = None


class ProjectEventsResponse(BaseModel):
    events: list[AgentEvent]


class PmLogEntry(BaseModel):
    log_id: str
    project_id: str
    action_type: str
    summary: str
    payload: dict
    actor: str
    metadata: dict
    created_at: str


class PmLogListResponse(BaseModel):
    logs: list[PmLogEntry]


class ResolveEventRequest(BaseModel):
    resolved_by: str = "pm_agent"


class MessageSendRequest(BaseModel):
    project_id: str
    conversation_id: str
    sender_type: str = "freelancer"
    sender_id: str
    sender_name: str
    content: str
    reply_to: str | None = None


class MessageResponse(BaseModel):
    message: Message


class ConversationCreateRequest(BaseModel):
    project_id: str
    conversation_type: str = "project_channel"
    title: str | None = None
    participants: list[str] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    conversation: Conversation


class ChatHistoryRequest(BaseModel):
    conversation_id: str
    limit: int = 50
    before_message_id: str | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[Message]
    has_more: bool


class ChatSummarizeRequest(BaseModel):
    conversation_id: str
    message_count: int | None = 50
    create_action_items: bool = True


class ChatSummarizeResponse(BaseModel):
    summary: ChatSummary
    context_record: ContextBankRecord
    events_created: list[AgentEvent] = Field(default_factory=list)


class MeetingCreateRequest(BaseModel):
    project_id: str
    title: str
    scheduled_at: str
    duration_minutes: int = 60
    participants: list[str] = Field(default_factory=list)


class MeetingResponse(BaseModel):
    meeting: Meeting


class MeetingCompleteRequest(BaseModel):
    transcript: str
    absentees: list[str] = Field(default_factory=list)


class MeetingCompleteResponse(BaseModel):
    meeting: Meeting
    mom: MinutesOfMeeting
    context_record: ContextBankRecord
    events_created: list[AgentEvent] = Field(default_factory=list)


class SecretarySuggestRequest(BaseModel):
    conversation_id: str
    current_message: str
    context_messages: int = 10


class SecretarySuggestResponse(BaseModel):
    suggestions: list[str]
    reasoning: str
    tone_analysis: str


class CVUploadRequest(BaseModel):
    user_id: str
    email: str
    full_name: str
    cv_text: str
    cv_format: str = "text"


class CVParseResponse(BaseModel):
    profile_id: str
    raw_extracted_data: dict
    parsed_profile: FreelancerProfile
    context_record: ContextBankRecord


class ProfileGenerateRequest(BaseModel):
    profile_id: str
    enhance_with_ai: bool = True


class ProfileGenerateResponse(BaseModel):
    profile: FreelancerProfile
    generated_summary: str
    generated_headline: str
    top_skills_highlight: list[str]
    context_record: ContextBankRecord


class ProfileUpdateRequest(BaseModel):
    headline: str | None = None
    bio: str | None = None
    hourly_rate: float | None = None
    availability_hours_per_week: int | None = None
    is_available: bool | None = None


class ProfileResponse(BaseModel):
    profile: FreelancerProfile


class ProfileSearchRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    min_hourly_rate: float | None = None
    max_hourly_rate: float | None = None
    available_only: bool = True
    limit: int = 20


class ProfileSearchResponse(BaseModel):
    profiles: list[FreelancerProfile]
    total_count: int


class MatchCreateRequest(BaseModel):
    project_id: str | None = None
    project_description: str
    required_skills: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    timeline_weeks: int | None = None
    top_k: int = 5


class MatchCreateResponse(BaseModel):
    request_id: str
    matches: list[MatchResult]
    context_record: ContextBankRecord


class MatchResultResponse(BaseModel):
    match_id: str
    profile: FreelancerProfile
    match_score: float
    match_reasoning: str
    skill_match_percentage: float
