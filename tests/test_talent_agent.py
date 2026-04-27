import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.talent_agent import TalentAgentService
from app.core.config import Settings
from app.main import create_app
from app.services.azure_search import AzureSearchContextBankIndex
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime, EmbeddingService
from app.services.profile_service import ProfileService


class ScriptedRuntime(BaseRuntime):
    def __init__(self, responses: dict[str, dict]) -> None:
        self._responses = responses

    @property
    def name(self) -> str:
        return "scripted-runtime"

    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        return json.dumps(self._responses.get(agent_name, {"error": "Unknown agent"}))


def build_test_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        context_bank_dir=tmp_path / "context_bank",
        use_microsoft_agent_framework=False,
    )
    runtime = ScriptedRuntime(
        responses={
            "cv_parser": {
                "location": "Jakarta, Indonesia",
                "timezone": "Asia/Jakarta",
                "languages": ["Indonesian", "English"],
                "hourly_rate": 25.0,
                "availability_hours_per_week": 30,
                "skills": [
                    {"name": "React", "category": "Frontend", "proficiency": "expert", "years_experience": 5},
                    {"name": "TypeScript", "category": "Frontend", "proficiency": "advanced", "years_experience": 4},
                    {"name": "Node.js", "category": "Backend", "proficiency": "intermediate", "years_experience": 3},
                ],
                "experiences": [
                    {
                        "company": "TechCorp Indonesia",
                        "role": "Senior Frontend Developer",
                        "start_date": "2021-01-01",
                        "end_date": None,
                        "is_current": True,
                        "description": "Leading frontend development for e-commerce platform",
                        "skills_used": ["React", "TypeScript", "Redux"],
                    }
                ],
                "portfolio": [
                    {
                        "title": "E-commerce Dashboard",
                        "description": "Built admin dashboard for inventory management",
                        "project_url": "https://example.com",
                        "skills_demonstrated": ["React", "TypeScript"],
                    }
                ],
            },
            "profile_generator": {
                "headline": "Expert React Developer | 5+ Years Building Scalable Web Apps",
                "bio": "Passionate frontend developer with expertise in React and TypeScript. Experienced in building e-commerce platforms and admin dashboards. Strong focus on clean code and user experience.",
                "summary": "React expert specializing in scalable web applications with 5+ years experience in e-commerce and dashboard development.",
                "top_skills": [
                    "React: Expert-level with 5 years building production apps",
                    "TypeScript: Strong typing and architecture skills",
                    "Node.js: Full-stack capabilities",
                ],
                "top_skills_summary": "React, TypeScript, Node.js, Redux, Frontend Architecture",
            },
        }
    )
    context_bank = ContextBankService(
        root_dir=settings.context_bank_dir,
        embedding_service=EmbeddingService(settings),
        search_index=AzureSearchContextBankIndex(settings),
    )
    profile_service = ProfileService(
        root_dir=settings.context_bank_dir,
        embedding_service=EmbeddingService(settings),
    )
    talent_service = TalentAgentService(
        runtime=runtime,
        profile_service=profile_service,
        context_bank=context_bank,
    )
    app = create_app(settings=settings, talent_service=talent_service)
    return TestClient(app)


def test_cv_upload_and_parse(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    cv_text = """
    John Doe
    Jakarta, Indonesia
    
    EXPERIENCE
    Senior Frontend Developer at TechCorp Indonesia (2021 - Present)
    - Leading frontend development for e-commerce platform
    - React, TypeScript, Redux
    
    SKILLS
    React (5 years), TypeScript (4 years), Node.js (3 years)
    
    LANGUAGES
    Indonesian, English
    
    RATE
    $25/hour, available 30 hours/week
    """

    response = client.post(
        "/api/v1/talent/signup/cv",
        json={
            "user_id": "user-123",
            "email": "john@example.com",
            "full_name": "John Doe",
            "cv_text": cv_text,
            "cv_format": "text",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "profile_id" in result
    assert result["parsed_profile"]["full_name"] == "John Doe"
    assert len(result["parsed_profile"]["skills"]) > 0


def test_profile_generation(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    cv_response = client.post(
        "/api/v1/talent/signup/cv",
        json={
            "user_id": "user-456",
            "email": "jane@example.com",
            "full_name": "Jane Smith",
            "cv_text": "Sample CV text here",
            "cv_format": "text",
        },
    )
    profile_id = cv_response.json()["profile_id"]

    generate_response = client.post(
        f"/api/v1/talent/profiles/{profile_id}/generate",
        json={"enhance_with_ai": True},
    )
    assert generate_response.status_code == 200
    result = generate_response.json()
    assert result["generated_headline"] != ""
    assert result["generated_summary"] != ""
    assert len(result["top_skills_highlight"]) > 0


def test_profile_crud(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    cv_response = client.post(
        "/api/v1/talent/signup/cv",
        json={
            "user_id": "user-crud",
            "email": "crud@example.com",
            "full_name": "CRUD Test",
            "cv_text": "CV content",
            "cv_format": "text",
        },
    )
    profile_id = cv_response.json()["profile_id"]

    get_response = client.get(f"/api/v1/talent/profiles/{profile_id}")
    assert get_response.status_code == 200
    assert get_response.json()["profile"]["full_name"] == "CRUD Test"

    get_by_user = client.get("/api/v1/talent/users/user-crud/profile")
    assert get_by_user.status_code == 200
    assert get_by_user.json()["profile"]["email"] == "crud@example.com"

    update_response = client.patch(
        f"/api/v1/talent/profiles/{profile_id}",
        json={
            "headline": "Updated Headline",
            "hourly_rate": 50.0,
            "is_available": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["profile"]["headline"] == "Updated Headline"
    assert update_response.json()["profile"]["hourly_rate"] == 50.0


def test_profile_search(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    for i in range(3):
        client.post(
            "/api/v1/talent/signup/cv",
            json={
                "user_id": f"user-search-{i}",
                "email": f"search{i}@example.com",
                "full_name": f"Search User {i}",
                "cv_text": f"CV with React skills {i}",
                "cv_format": "text",
            },
        )

    search_response = client.post(
        "/api/v1/talent/profiles/search",
        json={
            "skills": ["React"],
            "available_only": True,
            "limit": 10,
        },
    )
    assert search_response.status_code == 200
    result = search_response.json()
    assert len(result["profiles"]) > 0


def test_matchmaking(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    for i in range(3):
        client.post(
            "/api/v1/talent/signup/cv",
            json={
                "user_id": f"user-match-{i}",
                "email": f"match{i}@example.com",
                "full_name": f"Match User {i}",
                "cv_text": f"Developer with React and Node.js {i}",
                "cv_format": "text",
            },
        )

    match_response = client.post(
        "/api/v1/talent/match",
        json={
            "project_id": "proj-match",
            "project_description": "Need a React developer to build an e-commerce frontend",
            "required_skills": ["React", "TypeScript"],
            "budget_min": 20.0,
            "budget_max": 50.0,
            "timeline_weeks": 8,
            "top_k": 5,
        },
    )
    assert match_response.status_code == 200
    result = match_response.json()
    assert "request_id" in result
    assert len(result["matches"]) > 0
    assert result["matches"][0]["match_score"] > 0

    match_id = result["matches"][0]["match_id"]
    details_response = client.get(f"/api/v1/talent/matches/{match_id}")
    assert details_response.status_code == 200
    assert details_response.json()["match_id"] == match_id
    assert "profile" in details_response.json()
