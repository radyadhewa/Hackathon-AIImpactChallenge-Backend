from fastapi import APIRouter, Depends, Request

from app.agents.talent_agent import TalentAgentService
from app.models.api import (
    CVUploadRequest,
    CVParseResponse,
    ProfileGenerateRequest,
    ProfileGenerateResponse,
    ProfileResponse,
    ProfileSearchRequest,
    ProfileSearchResponse,
    ProfileUpdateRequest,
    MatchCreateRequest,
    MatchCreateResponse,
    MatchResultResponse,
)

router = APIRouter(prefix="/talent", tags=["Talent Agent"])


def get_talent_service(request: Request) -> TalentAgentService:
    return request.app.state.talent_service


@router.post("/signup/cv", response_model=CVParseResponse)
async def parse_cv(
    payload: CVUploadRequest,
    service: TalentAgentService = Depends(get_talent_service),
) -> CVParseResponse:
    return await service.parse_cv(payload)


@router.post("/profiles/{profile_id}/generate", response_model=ProfileGenerateResponse)
async def generate_profile(
    profile_id: str,
    payload: ProfileGenerateRequest,
    service: TalentAgentService = Depends(get_talent_service),
) -> ProfileGenerateResponse:
    payload.profile_id = profile_id
    return await service.generate_enhanced_profile(payload)


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    service: TalentAgentService = Depends(get_talent_service),
) -> ProfileResponse:
    return await service.get_profile(profile_id)


@router.get("/users/{user_id}/profile", response_model=ProfileResponse)
async def get_profile_by_user(
    user_id: str,
    service: TalentAgentService = Depends(get_talent_service),
) -> ProfileResponse:
    return await service.get_profile_by_user(user_id)


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    payload: ProfileUpdateRequest,
    service: TalentAgentService = Depends(get_talent_service),
) -> ProfileResponse:
    return await service.update_profile(profile_id, payload)


@router.post("/profiles/search", response_model=ProfileSearchResponse)
async def search_profiles(
    payload: ProfileSearchRequest,
    service: TalentAgentService = Depends(get_talent_service),
) -> ProfileSearchResponse:
    return await service.search_profiles(payload)


@router.post("/match", response_model=MatchCreateResponse)
async def find_matches(
    payload: MatchCreateRequest,
    service: TalentAgentService = Depends(get_talent_service),
) -> MatchCreateResponse:
    return await service.find_matches(payload)


@router.get("/matches/{match_id}", response_model=MatchResultResponse)
async def get_match_details(
    match_id: str,
    service: TalentAgentService = Depends(get_talent_service),
) -> MatchResultResponse:
    return await service.get_match_details(match_id)
