from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class FreelancerAvailability(BaseModel):
    name: str
    role: str
    hours_per_week: int = Field(ge=1)
    timezone: str
    skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class Milestone(BaseModel):
    name: str
    due_date: date | None = None
    success_definition: str | None = None


class ProjectOverview(BaseModel):
    project_id: str
    project_name: str
    client_name: str | None = None
    description: str
    scope: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    freelancers: list[FreelancerAvailability] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    timeline_notes: str | None = None


class ContextBankRecord(BaseModel):
    id: str
    project_id: str
    entry_type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    created_at: datetime


class TaskItem(BaseModel):
    task_id: str
    title: str
    description: str
    assigned_to: str
    estimated_hours: int = Field(ge=1)
    priority: str
    due_hint: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    recommended_references: list[str] = Field(default_factory=list)


class TaskBreakdownResult(BaseModel):
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)


class WorkCheckResult(BaseModel):
    verdict: str
    scope_alignment_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    improvement_actions: list[str] = Field(default_factory=list)
    reference_suggestions: list[str] = Field(default_factory=list)
    needs_escalation: bool = False
    escalation_message: str | None = None


class ProjectReport(BaseModel):
    summary: str
    progress_percent: int = Field(ge=0, le=100)
    overall_status: str
    wins: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    upcoming_actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    morale_coaching: list[str] = Field(default_factory=list)


class ProjectContextSnapshot(BaseModel):
    project_id: str
    overview: ProjectOverview | None = None
    recent_entries: list[ContextBankRecord] = Field(default_factory=list)


class TaskDependency(BaseModel):
    task_id: str
    depends_on: list[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    entry_id: str
    project_id: str
    entry_type: Literal["milestone", "task", "deadline"]
    title: str
    description: str
    start_date: datetime | None = None
    due_date: datetime | None = None
    assigned_to: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["not_started", "in_progress", "completed", "blocked"] = "not_started"
    estimated_hours: int = Field(default=0, ge=0)
    actual_hours: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectTimeline(BaseModel):
    project_id: str
    entries: list[TimelineEntry] = Field(default_factory=list)
    critical_path: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentEvent(BaseModel):
    event_id: str
    project_id: str
    source_agent: str
    event_type: Literal["escalation", "task_created", "task_completed", "help_needed", "timeline_update"]
    title: str
    description: str
    target_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class Message(BaseModel):
    message_id: str
    conversation_id: str
    project_id: str
    sender_type: Literal["freelancer", "client", "agent", "system"]
    sender_id: str
    sender_name: str
    content: str
    reply_to: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    edited_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    conversation_id: str
    project_id: str
    conversation_type: Literal["direct", "group", "project_channel"]
    title: str | None = None
    participants: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime | None = None
    is_active: bool = True


class Meeting(BaseModel):
    meeting_id: str
    project_id: str
    title: str
    scheduled_at: datetime
    duration_minutes: int
    participants: list[str] = Field(default_factory=list)
    status: Literal["scheduled", "ongoing", "completed", "cancelled"] = "scheduled"
    recording_url: str | None = None
    transcript: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class ActionItem(BaseModel):
    item_id: str
    meeting_id: str | None = None
    conversation_id: str | None = None
    project_id: str
    content: str
    assignee: str | None = None
    due_date: datetime | None = None
    status: Literal["pending", "in_progress", "completed"] = "pending"
    priority: Literal["high", "medium", "low"] = "medium"
    source_type: Literal["meeting", "chat"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class ChatSummary(BaseModel):
    summary_id: str
    conversation_id: str
    project_id: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    decisions_made: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    message_count: int = 0
    from_timestamp: datetime
    to_timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MinutesOfMeeting(BaseModel):
    mom_id: str
    meeting_id: str
    project_id: str
    meeting_title: str
    conducted_at: datetime
    participants: list[str] = Field(default_factory=list)
    absentees: list[str] = Field(default_factory=list)
    agenda: list[str] = Field(default_factory=list)
    key_discussions: list[str] = Field(default_factory=list)
    decisions_made: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    next_meeting: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Skill(BaseModel):
    name: str
    category: str | None = None
    proficiency: Literal["beginner", "intermediate", "advanced", "expert"] = "intermediate"
    years_experience: float | None = None
    verified: bool = False


class Experience(BaseModel):
    experience_id: str
    company: str | None = None
    role: str
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)


class PortfolioItem(BaseModel):
    item_id: str
    title: str
    description: str | None = None
    project_url: str | None = None
    thumbnail_url: str | None = None
    skills_demonstrated: list[str] = Field(default_factory=list)
    completion_date: date | None = None


class FreelancerProfile(BaseModel):
    profile_id: str
    user_id: str
    email: str
    full_name: str
    headline: str | None = None
    bio: str | None = None
    location: str | None = None
    timezone: str | None = None
    languages: list[str] = Field(default_factory=list)
    hourly_rate: float | None = None
    availability_hours_per_week: int | None = None
    skills: list[Skill] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    portfolio: list[PortfolioItem] = Field(default_factory=list)
    profile_embedding: list[float] | None = None
    profile_summary: str | None = None
    top_skills_summary: str | None = None
    match_score: float | None = None
    is_available: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchRequest(BaseModel):
    request_id: str
    project_id: str | None = None
    project_description: str
    required_skills: list[str] = Field(default_factory=list)
    budget_range: dict[str, float] | None = None
    timeline_weeks: int | None = None
    request_embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchResult(BaseModel):
    match_id: str
    request_id: str
    profile_id: str
    match_score: float
    match_reasoning: str
    skill_match_percentage: float
    experience_relevance_score: float
    availability_match: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

