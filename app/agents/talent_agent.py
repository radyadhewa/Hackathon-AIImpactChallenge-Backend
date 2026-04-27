from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.agents.prompts import (
    CV_PARSER_INSTRUCTIONS,
    PROFILE_GENERATOR_INSTRUCTIONS,
)
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
from app.models.domain import (
    ContextBankRecord,
    Experience,
    FreelancerProfile,
    MatchRequest,
    MatchResult,
    PortfolioItem,
    Skill,
)
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime
from app.services.profile_service import ProfileService

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class TalentAgentService:
    def __init__(
        self,
        runtime: BaseRuntime,
        profile_service: ProfileService,
        context_bank: ContextBankService,
    ) -> None:
        self._runtime = runtime
        self._profile_service = profile_service
        self._context_bank = context_bank

    @property
    def runtime_name(self) -> str:
        return self._runtime.name

    async def parse_cv(self, payload: CVUploadRequest) -> CVParseResponse:
        existing_profile = await self._profile_service.get_profile_by_user_id(payload.user_id)
        if existing_profile:
            raise HTTPException(status_code=409, detail="Profile already exists for this user")

        prompt = json.dumps({
            "cv_text": payload.cv_text[:10000],
            "format": payload.cv_format,
        })

        raw = await self._runtime.generate(
            "cv_parser",
            CV_PARSER_INSTRUCTIONS,
            prompt,
        )

        parsed = self._parse_json(raw)

        profile = await self._create_profile_from_parsed_data(
            user_id=payload.user_id,
            email=payload.email,
            full_name=payload.full_name,
            parsed_data=parsed,
        )

        record = await self._context_bank.add_record(
            project_id="talent_pool",
            entry_type="cv_parsed",
            title=f"CV parsed for {profile.full_name}",
            content=json.dumps({
                "profile_id": profile.profile_id,
                "user_id": payload.user_id,
                "extracted_data": parsed,
            }),
            tags=["talent", "cv-parse", "signup"],
            metadata={
                "profile_id": profile.profile_id,
                "user_id": payload.user_id,
                "skills_count": len(profile.skills),
            },
            source="cv_parser",
        )

        return CVParseResponse(
            profile_id=profile.profile_id,
            raw_extracted_data=parsed,
            parsed_profile=profile,
            context_record=record,
        )

    async def _create_profile_from_parsed_data(
        self,
        user_id: str,
        email: str,
        full_name: str,
        parsed_data: dict,
    ) -> FreelancerProfile:
        profile = await self._profile_service.create_profile(
            user_id=user_id,
            email=email,
            full_name=full_name,
        )

        profile.location = parsed_data.get("location")
        profile.timezone = parsed_data.get("timezone")
        profile.languages = parsed_data.get("languages", [])
        profile.hourly_rate = parsed_data.get("hourly_rate")
        profile.availability_hours_per_week = parsed_data.get("availability_hours_per_week")

        for skill_data in parsed_data.get("skills", []):
            skill = Skill(
                name=skill_data["name"],
                category=skill_data.get("category"),
                proficiency=skill_data.get("proficiency", "intermediate"),
                years_experience=skill_data.get("years_experience"),
            )
            profile.skills.append(skill)

        for exp_data in parsed_data.get("experiences", []):
            start_date = None
            end_date = None
            if exp_data.get("start_date"):
                try:
                    start_date = date.fromisoformat(exp_data["start_date"])
                except ValueError:
                    pass
            if exp_data.get("end_date"):
                try:
                    end_date = date.fromisoformat(exp_data["end_date"])
                except ValueError:
                    pass

            experience = Experience(
                experience_id=str(uuid.uuid4()),
                company=exp_data.get("company"),
                role=exp_data["role"],
                start_date=start_date,
                end_date=end_date,
                is_current=exp_data.get("is_current", False),
                description=exp_data.get("description"),
                skills_used=exp_data.get("skills_used", []),
            )
            profile.experiences.append(experience)

        for portfolio_data in parsed_data.get("portfolio", []):
            portfolio_item = PortfolioItem(
                item_id=str(uuid.uuid4()),
                title=portfolio_data["title"],
                description=portfolio_data.get("description"),
                project_url=portfolio_data.get("project_url"),
                skills_demonstrated=portfolio_data.get("skills_demonstrated", []),
            )
            profile.portfolio.append(portfolio_item)

        await self._profile_service.update_profile(profile)
        return profile

    async def generate_enhanced_profile(
        self,
        payload: ProfileGenerateRequest,
    ) -> ProfileGenerateResponse:
        profile = await self._profile_service.get_profile(payload.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        if not payload.enhance_with_ai:
            return ProfileGenerateResponse(
                profile=profile,
                generated_summary=profile.bio or "",
                generated_headline=profile.headline or "",
                top_skills_highlight=[s.name for s in profile.skills[:5]],
                context_record=None,
            )

        prompt = json.dumps({
            "full_name": profile.full_name,
            "skills": [{"name": s.name, "proficiency": s.proficiency} for s in profile.skills],
            "experiences": [
                {
                    "role": e.role,
                    "company": e.company,
                    "description": e.description,
                }
                for e in profile.experiences[:5]
            ],
            "portfolio": [
                {
                    "title": p.title,
                    "description": p.description,
                }
                for p in profile.portfolio[:3]
            ],
        })

        raw = await self._runtime.generate(
            "profile_generator",
            PROFILE_GENERATOR_INSTRUCTIONS,
            prompt,
        )

        generated = self._parse_json(raw)

        profile.headline = generated.get("headline", profile.headline)
        profile.bio = generated.get("bio", profile.bio)
        profile.profile_summary = generated.get("summary", profile.profile_summary)
        profile.top_skills_summary = generated.get("top_skills_summary", profile.top_skills_summary)

        await self._profile_service.save_profile_with_embedding(profile)

        record = await self._context_bank.add_record(
            project_id="talent_pool",
            entry_type="profile_enhanced",
            title=f"Enhanced profile for {profile.full_name}",
            content=json.dumps({
                "profile_id": profile.profile_id,
                "generated_headline": profile.headline,
                "generated_summary": profile.profile_summary,
            }),
            tags=["talent", "profile-enhance"],
            metadata={"profile_id": profile.profile_id},
            source="profile_generator",
        )

        return ProfileGenerateResponse(
            profile=profile,
            generated_summary=profile.profile_summary or "",
            generated_headline=profile.headline or "",
            top_skills_highlight=generated.get("top_skills", []),
            context_record=record,
        )

    async def get_profile(self, profile_id: str) -> ProfileResponse:
        profile = await self._profile_service.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return ProfileResponse(profile=profile)

    async def get_profile_by_user(self, user_id: str) -> ProfileResponse:
        profile = await self._profile_service.get_profile_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return ProfileResponse(profile=profile)

    async def update_profile(
        self,
        profile_id: str,
        payload: ProfileUpdateRequest,
    ) -> ProfileResponse:
        profile = await self._profile_service.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        if payload.headline is not None:
            profile.headline = payload.headline
        if payload.bio is not None:
            profile.bio = payload.bio
        if payload.hourly_rate is not None:
            profile.hourly_rate = payload.hourly_rate
        if payload.availability_hours_per_week is not None:
            profile.availability_hours_per_week = payload.availability_hours_per_week
        if payload.is_available is not None:
            profile.is_available = payload.is_available

        await self._profile_service.save_profile_with_embedding(profile)
        return ProfileResponse(profile=profile)

    async def search_profiles(self, payload: ProfileSearchRequest) -> ProfileSearchResponse:
        if payload.skills:
            profiles = await self._profile_service.search_profiles_by_skills(
                skills=payload.skills,
                available_only=payload.available_only,
                limit=payload.limit,
            )
        else:
            profiles = await self._profile_service.list_profiles(
                available_only=payload.available_only,
                limit=payload.limit,
            )

        filtered_profiles = []
        for profile in profiles:
            if payload.min_hourly_rate is not None:
                if profile.hourly_rate is None or profile.hourly_rate < payload.min_hourly_rate:
                    continue
            if payload.max_hourly_rate is not None:
                if profile.hourly_rate is None or profile.hourly_rate > payload.max_hourly_rate:
                    continue
            filtered_profiles.append(profile)

        return ProfileSearchResponse(
            profiles=filtered_profiles,
            total_count=len(filtered_profiles),
        )

    async def find_matches(self, payload: MatchCreateRequest) -> MatchCreateResponse:
        budget_range = None
        if payload.budget_min is not None or payload.budget_max is not None:
            budget_range = {
                "min": payload.budget_min or 0,
                "max": payload.budget_max or float("inf"),
            }

        match_request = await self._profile_service.create_match_request(
            project_description=payload.project_description,
            required_skills=payload.required_skills,
            project_id=payload.project_id,
            budget_range=budget_range,
            timeline_weeks=payload.timeline_weeks,
        )

        matches = await self._profile_service.find_matches(
            match_request=match_request,
            top_k=payload.top_k,
        )

        record = await self._context_bank.add_record(
            project_id=payload.project_id or "talent_pool",
            entry_type="match_request",
            title=f"Match request for project",
            content=json.dumps({
                "request_id": match_request.request_id,
                "project_id": payload.project_id,
                "required_skills": payload.required_skills,
                "matches_found": len(matches),
            }),
            tags=["talent", "matchmaking"],
            metadata={
                "request_id": match_request.request_id,
                "project_id": payload.project_id,
                "matches_count": len(matches),
            },
            source="talent_agent",
        )

        return MatchCreateResponse(
            request_id=match_request.request_id,
            matches=matches,
            context_record=record,
        )

    async def get_match_details(self, match_id: str) -> MatchResultResponse:
        matches_dir = self._profile_service._matches_dir()
        match_file = matches_dir / f"{match_id}.json"

        if not match_file.exists():
            raise HTTPException(status_code=404, detail="Match not found")

        def _read() -> MatchResult:
            return MatchResult.model_validate_json(match_file.read_text(encoding="utf-8"))

        match = await asyncio.to_thread(_read)
        profile = await self._profile_service.get_profile(match.profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return MatchResultResponse(
            match_id=match.match_id,
            profile=profile,
            match_score=match.match_score,
            match_reasoning=match.match_reasoning,
            skill_match_percentage=match.skill_match_percentage,
        )

    @staticmethod
    def _parse_json(raw_response: str) -> dict:
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            match = JSON_OBJECT_PATTERN.search(raw_response)
            if match:
                return json.loads(match.group(0))
        raise HTTPException(
            status_code=502,
            detail="Agent runtime did not return valid JSON.",
        )
