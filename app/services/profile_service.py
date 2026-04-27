from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models.domain import FreelancerProfile, MatchRequest, MatchResult, Skill
from app.services.llm import EmbeddingService


class ProfileService:
    def __init__(
        self,
        root_dir: Path,
        embedding_service: EmbeddingService,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._embedding_service = embedding_service

    def _profiles_dir(self) -> Path:
        return self._root_dir / "profiles"

    def _profile_file(self, profile_id: str) -> Path:
        return self._profiles_dir() / f"{profile_id}.json"

    def _matches_dir(self) -> Path:
        return self._root_dir / "matches"

    def _match_file(self, match_id: str) -> Path:
        return self._matches_dir() / f"{match_id}.json"

    async def create_profile(
        self,
        user_id: str,
        email: str,
        full_name: str,
    ) -> FreelancerProfile:
        profile = FreelancerProfile(
            profile_id=str(uuid.uuid4()),
            user_id=user_id,
            email=email,
            full_name=full_name,
        )

        profile_file = self._profile_file(profile.profile_id)

        def _write() -> None:
            profile_file.parent.mkdir(parents=True, exist_ok=True)
            profile_file.write_text(
                profile.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return profile

    async def get_profile(self, profile_id: str) -> FreelancerProfile | None:
        profile_file = self._profile_file(profile_id)
        if not profile_file.exists():
            return None

        def _read() -> FreelancerProfile:
            return FreelancerProfile.model_validate_json(profile_file.read_text(encoding="utf-8"))

        return await asyncio.to_thread(_read)

    async def get_profile_by_user_id(self, user_id: str) -> FreelancerProfile | None:
        profiles_dir = self._profiles_dir()
        if not profiles_dir.exists():
            return None

        def _find() -> FreelancerProfile | None:
            for profile_file in profiles_dir.glob("*.json"):
                profile = FreelancerProfile.model_validate_json(profile_file.read_text(encoding="utf-8"))
                if profile.user_id == user_id:
                    return profile
            return None

        return await asyncio.to_thread(_find)

    async def update_profile(self, profile: FreelancerProfile) -> FreelancerProfile:
        profile.updated_at = datetime.now(timezone.utc)
        profile_file = self._profile_file(profile.profile_id)

        def _write() -> None:
            profile_file.write_text(
                profile.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return profile

    async def generate_profile_embedding(self, profile: FreelancerProfile) -> list[float] | None:
        profile_text = self._profile_to_text(profile)
        embedding = await self._embedding_service.embed_text(profile_text)
        return embedding

    def _profile_to_text(self, profile: FreelancerProfile) -> str:
        parts = [
            f"Name: {profile.full_name}",
            f"Headline: {profile.headline or 'N/A'}",
            f"Bio: {profile.bio or 'N/A'}",
            f"Skills: {', '.join(s.name for s in profile.skills)}",
            f"Location: {profile.location or 'N/A'}",
            f"Languages: {', '.join(profile.languages)}",
        ]

        if profile.experiences:
            parts.append("Experience:")
            for exp in profile.experiences:
                parts.append(f"  - {exp.role} at {exp.company or 'Freelance'}: {exp.description or 'N/A'}")

        return "\n".join(parts)

    async def save_profile_with_embedding(
        self,
        profile: FreelancerProfile,
    ) -> FreelancerProfile:
        embedding = await self.generate_profile_embedding(profile)
        if embedding:
            profile.profile_embedding = embedding
        return await self.update_profile(profile)

    async def list_profiles(
        self,
        available_only: bool = True,
        limit: int = 100,
    ) -> list[FreelancerProfile]:
        profiles_dir = self._profiles_dir()
        if not profiles_dir.exists():
            return []

        def _read_all() -> list[FreelancerProfile]:
            items: list[FreelancerProfile] = []
            for profile_file in profiles_dir.glob("*.json"):
                profile = FreelancerProfile.model_validate_json(profile_file.read_text(encoding="utf-8"))
                if not available_only or profile.is_available:
                    items.append(profile)
            items.sort(key=lambda p: p.updated_at, reverse=True)
            return items[:limit]

        return await asyncio.to_thread(_read_all)

    async def search_profiles_by_skills(
        self,
        skills: list[str],
        available_only: bool = True,
        limit: int = 20,
    ) -> list[FreelancerProfile]:
        profiles = await self.list_profiles(available_only=available_only, limit=100)
        skill_set = {s.lower() for s in skills}

        scored: list[tuple[int, FreelancerProfile]] = []
        for profile in profiles:
            profile_skills = {s.name.lower() for s in profile.skills}
            match_count = len(skill_set & profile_skills)
            if match_count > 0:
                scored.append((match_count, profile))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    async def create_match_request(
        self,
        project_description: str,
        required_skills: list[str],
        project_id: str | None = None,
        budget_range: dict[str, float] | None = None,
        timeline_weeks: int | None = None,
    ) -> MatchRequest:
        request = MatchRequest(
            request_id=str(uuid.uuid4()),
            project_id=project_id,
            project_description=project_description,
            required_skills=required_skills,
            budget_range=budget_range,
            timeline_weeks=timeline_weeks,
        )

        request_text = f"{project_description}\nRequired skills: {', '.join(required_skills)}"
        embedding = await self._embedding_service.embed_text(request_text)
        if embedding:
            request.request_embedding = embedding

        return request

    async def find_matches(
        self,
        match_request: MatchRequest,
        top_k: int = 5,
    ) -> list[MatchResult]:
        profiles = await self.list_profiles(available_only=True, limit=100)

        if not match_request.request_embedding:
            match_request.request_embedding = await self._embedding_service.embed_text(
                f"{match_request.project_description}\nSkills: {', '.join(match_request.required_skills)}"
            )

        if not match_request.request_embedding:
            return []

        scored: list[tuple[float, FreelancerProfile]] = []
        for profile in profiles:
            if profile.profile_embedding:
                similarity = self._cosine_similarity(
                    match_request.request_embedding,
                    profile.profile_embedding,
                )
                scored.append((similarity, profile))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_profiles = scored[:top_k]

        matches: list[MatchResult] = []
        for similarity, profile in top_profiles:
            skill_match_pct = self._calculate_skill_match(match_request.required_skills, profile.skills)

            match = MatchResult(
                match_id=str(uuid.uuid4()),
                request_id=match_request.request_id,
                profile_id=profile.profile_id,
                match_score=similarity,
                match_reasoning=self._generate_match_reasoning(match_request, profile),
                skill_match_percentage=skill_match_pct,
                experience_relevance_score=similarity,
                availability_match=profile.is_available,
            )
            matches.append(match)

            match_file = self._match_file(match.match_id)

            def _write(m: MatchResult = match) -> None:
                match_file.parent.mkdir(parents=True, exist_ok=True)
                match_file.write_text(
                    m.model_dump_json(indent=2),
                    encoding="utf-8",
                )

            await asyncio.to_thread(_write)

        return matches

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _calculate_skill_match(
        self,
        required_skills: list[str],
        profile_skills: list[Skill],
    ) -> float:
        if not required_skills:
            return 100.0

        required_set = {s.lower() for s in required_skills}
        profile_set = {s.name.lower() for s in profile_skills}

        matches = len(required_set & profile_set)
        return (matches / len(required_set)) * 100.0

    def _generate_match_reasoning(
        self,
        match_request: MatchRequest,
        profile: FreelancerProfile,
    ) -> str:
        matched_skills = []
        for req_skill in match_request.required_skills:
            for profile_skill in profile.skills:
                if req_skill.lower() == profile_skill.name.lower():
                    matched_skills.append(profile_skill.name)

        parts = [f"Strong match based on skills: {', '.join(matched_skills)}."]

        if profile.experiences:
            parts.append(f"Has {len(profile.experiences)} relevant experiences.")

        if profile.hourly_rate and match_request.budget_range:
            min_budget = match_request.budget_range.get("min", 0)
            max_budget = match_request.budget_range.get("max", float("inf"))
            if min_budget <= profile.hourly_rate <= max_budget:
                parts.append("Rate fits within budget range.")

        return " ".join(parts)
