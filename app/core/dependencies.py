from pathlib import Path

from app.agents.pm_agent import PMAgentService
from app.agents.secretary_agent import SecretaryAgentService
from app.agents.talent_agent import TalentAgentService
from app.core.config import Settings
from app.services.azure_search import AzureSearchContextBankIndex
from app.services.chat_service import ChatService
from app.services.context_bank import ContextBankService
from app.services.llm import EmbeddingService, LocalTemplateRuntime, MicrosoftAgentRuntime
from app.services.pm_log_store import PmLogStore
from app.services.profile_service import ProfileService
from app.services.timeline_service import TimelineService


def _build_context_bank(settings: Settings) -> ContextBankService:
    embedding_service = EmbeddingService(settings)
    search_index = AzureSearchContextBankIndex(settings)
    return ContextBankService(
        root_dir=settings.context_bank_dir,
        embedding_service=embedding_service,
        search_index=search_index,
        settings=settings,
    )


def _build_runtime(settings: Settings):
    if (
        settings.use_microsoft_agent_framework
        and settings.azure_foundry_endpoint
        and settings.azure_foundry_chat_deployment
    ):
        try:
            return MicrosoftAgentRuntime(settings)
        except RuntimeError:
            return LocalTemplateRuntime()
    return LocalTemplateRuntime()


def build_pm_service(settings: Settings) -> PMAgentService:
    context_bank = _build_context_bank(settings)
    timeline_service = TimelineService(context_bank)
    runtime = _build_runtime(settings)
    log_store = PmLogStore(settings)

    return PMAgentService(
        runtime=runtime,
        context_bank=context_bank,
        timeline_service=timeline_service,
        log_store=log_store,
    )


def build_secretary_service(settings: Settings) -> SecretaryAgentService:
    context_bank = _build_context_bank(settings)
    chat_service = ChatService(root_dir=settings.context_bank_dir, settings=settings)
    runtime = _build_runtime(settings)

    return SecretaryAgentService(
        runtime=runtime,
        chat_service=chat_service,
        context_bank=context_bank,
    )


def build_talent_service(settings: Settings) -> TalentAgentService:
    context_bank = _build_context_bank(settings)
    embedding_service = EmbeddingService(settings)
    profile_service = ProfileService(
        root_dir=settings.context_bank_dir,
        embedding_service=embedding_service,
        settings=settings,
    )
    runtime = _build_runtime(settings)

    return TalentAgentService(
        runtime=runtime,
        profile_service=profile_service,
        context_bank=context_bank,
    )
