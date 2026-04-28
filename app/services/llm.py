from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from app.core.config import Settings

try:
    from agent_framework.azure import AzureOpenAIChatClient
except ImportError:  # pragma: no cover
    AzureOpenAIChatClient = None

try:
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover
    DefaultAzureCredential = None

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None


class BaseRuntime(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        raise NotImplementedError


class MicrosoftAgentRuntime(BaseRuntime):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "microsoft-agent-framework"

    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        if AzureOpenAIChatClient is None:
            raise RuntimeError(
                "agent-framework is not installed. Install dependencies before using the Azure runtime."
            )

        client_kwargs: dict[str, object] = {
            "endpoint": self._settings.azure_foundry_endpoint,
            "deployment_name": self._settings.azure_foundry_chat_deployment,
        }
        if self._settings.azure_foundry_api_version:
            client_kwargs["api_version"] = self._settings.azure_foundry_api_version
        if self._settings.azure_foundry_api_key_value:
            client_kwargs["api_key"] = self._settings.azure_foundry_api_key_value
        elif self._settings.azure_use_default_credential and DefaultAzureCredential:
            client_kwargs["credential"] = DefaultAzureCredential()
        else:
            raise RuntimeError(
                "Azure runtime requires either AZURE_FOUNDRY_API_KEY or AZURE_USE_DEFAULT_CREDENTIAL=true."
            )

        client = AzureOpenAIChatClient(**client_kwargs)
        agent = client.create_agent(name=agent_name, instructions=instructions)
        response = await agent.run(payload)
        return getattr(response, "text", None) or str(response)


class LocalTemplateRuntime(BaseRuntime):
    @property
    def name(self) -> str:
        return "local-template-runtime"

    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        data = json.loads(payload)

        if agent_name == "task_breakdown":
            overview = data.get("project_overview") or {}
            freelancers = overview.get("freelancers") or []
            source_material = data.get("source_material", "")
            tasks = []
            for index, freelancer in enumerate(freelancers[:4], start=1):
                tasks.append(
                    {
                        "task_id": f"TASK-{index}",
                        "title": f"{freelancer['role']} workstream",
                        "description": (
                            f"Convert the delivery goal into a focused workstream for {freelancer['name']}. "
                            f"Anchor execution to this brief: {source_material[:140]}"
                        ),
                        "assigned_to": freelancer["name"],
                        "estimated_hours": max(4, freelancer["hours_per_week"] // 2),
                        "priority": "high" if index == 1 else "medium",
                        "due_hint": "This week",
                        "dependencies": ["Shared project kickoff"] if index > 1 else [],
                        "acceptance_criteria": [
                            "Work is aligned to scope",
                            "Progress is documented in the context bank",
                        ],
                        "recommended_references": [
                            "Reuse the client brief",
                            "Check the latest PM context updates",
                        ],
                    }
                )

            return json.dumps(
                {
                    "summary": "Local fallback created a starter work breakdown. Replace with Azure-backed runtime for production quality planning.",
                    "assumptions": [
                        "Freelancer capacity is based on weekly hours only.",
                        "Dependencies are inferred heuristically in local mode.",
                    ],
                    "tasks": tasks or [
                        {
                            "task_id": "TASK-1",
                            "title": "Initial PM scoping",
                            "description": "Clarify deliverables, timeline, and dependencies.",
                            "assigned_to": "PM Agent",
                            "estimated_hours": 6,
                            "priority": "high",
                            "due_hint": "Immediately",
                            "dependencies": [],
                            "acceptance_criteria": [
                                "Project scope is decomposed into actionable tasks",
                            ],
                            "recommended_references": [
                                "Project brief",
                            ],
                        }
                    ],
                }
            )

        if agent_name == "work_checker":
            scope_reference = data.get("scope_reference", "")
            deliverable_artifact = data.get("deliverable_artifact", "")
            shared_words = set(scope_reference.lower().split()) & set(
                deliverable_artifact.lower().split()
            )
            score = min(95, max(45, len(shared_words) * 4))
            verdict = "approved" if score >= 75 else "revise"
            return json.dumps(
                {
                    "verdict": verdict,
                    "scope_alignment_score": score,
                    "summary": "Local fallback reviewed the deliverable against the provided scope reference.",
                    "strengths": [
                        "Deliverable was checked against scope keywords.",
                    ],
                    "gaps": [] if verdict == "approved" else ["Add more explicit scope coverage."],
                    "improvement_actions": [
                        "Map each deliverable section to the scope reference.",
                        "Add a short self-review before submission.",
                    ],
                    "reference_suggestions": [
                        "Re-read the project brief and acceptance criteria.",
                    ],
                    "needs_escalation": score < 55,
                    "escalation_message": (
                        "Scope mismatch is large enough to escalate to the PM."
                        if score < 55
                        else None
                    ),
                }
            )

        if agent_name == "reporter":
            recent_entries = data.get("recent_entries") or []
            progress = min(90, 15 + len(recent_entries) * 10)
            blockers = []
            if not recent_entries:
                blockers.append("No project updates have been recorded yet.")
            return json.dumps(
                {
                    "summary": "Local fallback generated a project health snapshot from the current context bank.",
                    "progress_percent": progress,
                    "overall_status": "on_track" if progress >= 50 else "watch",
                    "wins": ["Context bank is active and PM automation is scaffolded."],
                    "blockers": blockers,
                    "upcoming_actions": [
                        "Record more delivery updates from freelancers.",
                        "Run work checks on completed tasks.",
                    ],
                    "risks": [
                        "Local fallback heuristics are not a substitute for Azure-backed reasoning.",
                    ],
                    "escalations": [],
                    "morale_coaching": [
                        "Keep updates concise and async-friendly so strangers can coordinate faster.",
                    ],
                }
            )

        raise ValueError(f"Unsupported local runtime agent: {agent_name}")


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    async def embed_text(self, text: str) -> list[float] | None:
        if (
            AsyncOpenAI is None
            or not self._settings.azure_foundry_endpoint
            or not self._settings.azure_foundry_embedding_deployment
            or not self._settings.azure_foundry_api_key_value
        ):
            return None

        client = AsyncOpenAI(
            api_key=self._settings.azure_foundry_api_key_value,
            base_url=f"{self._settings.azure_foundry_endpoint.rstrip('/')}/openai/v1/",
        )
        try:
            response = await client.embeddings.create(
                model=self._settings.azure_foundry_embedding_deployment,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:  # pragma: no cover - network dependent
            self._logger.warning("Embedding request failed: %s", exc)
            return None
