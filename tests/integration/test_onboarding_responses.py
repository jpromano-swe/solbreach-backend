from httpx import AsyncClient
from sqlalchemy import select

from app.modules.analytics.infrastructure.database.models import AnalyticsEventModel


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@solbreach.app", "password": "admin-password"},
    )
    assert response.status_code == 200
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_onboarding_responses_accepts_flexible_beta_payload(
    seeded_client: AsyncClient,
) -> None:
    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json={
            "walletAddress": "OnboardingWallet1111111111111111111111",
            "step": "goals",
            "completed": False,
            "responses": {
                "experience": "beginner",
                "goals": ["learn_solana_security", "practice_exploits"],
            },
            "metadata": {"section": "beta-access"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["walletAddress"] == "OnboardingWallet1111111111111111111111"
    assert body["data"]["userId"] is None
    assert body["data"]["step"] == "goals"
    assert body["data"]["responses"]["experience"] == "beginner"
    assert body["data"]["metadata"] == {"section": "beta-access"}


async def test_onboarding_responses_accepts_single_question_shape(
    seeded_client: AsyncClient,
) -> None:
    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json={
            "walletAddress": "SingleQuestionWallet111111111111111111",
            "questionId": "security_goal",
            "questionText": "What do you want to learn?",
            "answer": "Anchor account validation",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["responses"] == {
        "questionId": "security_goal",
        "questionText": "What do you want to learn?",
        "answer": "Anchor account validation",
    }


def _v2_payload() -> dict:
    return {
        "profile": "solana_developer",
        "realExperience": [
            "built_simple_project",
            "rust_experience",
            "rust_experience",
        ],
        "blockchainSecurityProfile": "no_security_background",
        "preferredFormats": ["guided_modules", "research_labs"],
        "securityLearningAttempt": "interested_not_started",
        "studyTechniques": ["official_docs", "small_projects"],
        "difficultAreas": ["security_mindset", "hands_on_practice"],
        "hardestPracticeStep": (
            "I understand examples, but I do not know how to test the issue myself."
        ),
        "practiceSignals": ["execute_exploit", "see_state_changes"],
        "securityRelevance": 5,
        "betaIntent": "try_this_week",
        "contactName": "Juan",
        "preferredContactChannel": "telegram",
        "contact": "@username",
        "source": "landing_onboarding",
        "utmSource": None,
        "utmMedium": None,
        "utmCampaign": None,
    }


async def test_onboarding_responses_accepts_v2_payload(
    client_with_session_factory,
) -> None:
    seeded_client, session_factory = client_with_session_factory
    payload = _v2_payload()
    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["schemaVersion"] == 2
    assert body["profile"] == "solana_developer"
    assert body["realExperience"] == ["built_simple_project", "rust_experience"]
    assert body["blockchainSecurityProfile"] == "no_security_background"
    assert body["securityLearningAttempt"] == "interested_not_started"
    assert body["securityRelevance"] == 5
    assert body["betaIntent"] == "try_this_week"
    assert body["contactName"] == "Juan"
    assert body["responses"]["hardestPracticeStep"] == payload["hardestPracticeStep"]

    async with session_factory() as session:
        result = await session.execute(
            select(AnalyticsEventModel).where(
                AnalyticsEventModel.event_type == "onboarding_response_submitted"
            )
        )
        event = result.scalar_one()
    assert event.metadata_json == {
        "schemaVersion": 2,
        "profile": "solana_developer",
        "blockchainSecurityProfile": "no_security_background",
        "securityLearningAttempt": "interested_not_started",
        "securityRelevance": 5,
        "betaIntent": "try_this_week",
        "realExperienceCount": 2,
        "preferredFormatsCount": 2,
        "studyTechniquesCount": 2,
        "difficultAreasCount": 2,
        "practiceSignalsCount": 2,
    }


async def test_onboarding_responses_accepts_legacy_profile_alias(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload["profile"] = "protocol_or_technical_team"

    response = await seeded_client.post("/api/v1/onboarding/responses", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["profile"] == "backend_or_rust_developer"


async def test_onboarding_responses_accepts_educator_profile_alias(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload["profile"] = "educator_bootcamp_community"

    response = await seeded_client.post("/api/v1/onboarding/responses", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["profile"] == "community_bootcamp_or_team"


async def test_onboarding_responses_accepts_security_researcher_profile_alias(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload["profile"] = "security_researcher"

    response = await seeded_client.post("/api/v1/onboarding/responses", json=payload)

    assert response.status_code == 201
    assert response.json()["data"]["profile"] == "security_researcher_or_auditor"


async def test_onboarding_responses_accepts_legacy_serializer_payload(
    seeded_client: AsyncClient,
) -> None:
    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json={
            "additionalNotes": "hardest=Ver casos puntuales.\nsecurity_relevance=3/5",
            "betaIntent": "try_this_week",
            "contact": "@zircondioxde",
            "currentLearningSources": ["mentorship", "ai_tools"],
            "feedbackWillingness": "form",
            "futureLabsInterest": (
                "profile=solana_developer;"
                "security_profile=ctf_or_audit_learning;"
                "security_attempt=interested_not_started;"
                "experience=built_simple_project;"
                "study=mentor_or_peer_feedback,ai_assisted;"
                "areas=rust_anchor_basics,hands_on_practice;"
                "formats=audit_environments;"
                "practice=validation_checks,execute_exploit;"
                "security_relevance=3"
            ),
            "guidedLabUsefulness": 3,
            "mainGoal": ["prepare_for_cohorts_or_audits"],
            "name": "Juan",
            "organizationName": None,
            "preferredContactChannel": "telegram",
            "profile": "solana_developer",
            "securityExperience": "joined_ctfs",
            "solanaLevel": "built_simple_project",
            "source": "landing_onboarding",
            "utmCampaign": None,
            "utmMedium": None,
            "utmSource": None,
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["profile"] == "solana_developer"
    assert body["realExperience"] == ["built_simple_project"]
    assert body["blockchainSecurityProfile"] == "ctf_or_audit_learning"
    assert body["preferredFormats"] == ["audit_environments"]
    assert body["securityLearningAttempt"] == "interested_not_started"
    assert body["studyTechniques"] == ["mentor_or_peer_feedback", "ai_assisted"]
    assert body["difficultAreas"] == ["rust_anchor_basics", "hands_on_practice"]
    assert body["hardestPracticeStep"] == "Ver casos puntuales."
    assert body["practiceSignals"] == ["validation_checks", "execute_exploit"]
    assert body["securityRelevance"] == 3
    assert body["contactName"] == "Juan"
    assert body["contact"] == "@zircondioxde"


async def test_onboarding_responses_accepts_legacy_only_payload_without_kv_blob(
    seeded_client: AsyncClient,
) -> None:
    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json={
            "additionalNotes": "hardest=Browser compatibility probe legacy only.\nsecurity_relevance=3/5",
            "betaIntent": "not_now",
            "contact": "not_provided",
            "currentLearningSources": ["audit_reports"],
            "feedbackWillingness": "not_now",
            "guidedLabUsefulness": 3,
            "mainGoal": ["understand_real_vulnerabilities"],
            "name": "Probe Legacy",
            "organizationName": None,
            "preferredContactChannel": "email",
            "profile": "protocol_or_technical_team",
            "securityExperience": "read_writeups_or_audit_reports",
            "solanaLevel": "worked_with_anchor_or_programs",
            "source": "landing_onboarding",
            "utmCampaign": None,
            "utmMedium": None,
            "utmSource": None,
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["profile"] == "backend_or_rust_developer"
    assert body["realExperience"] == ["worked_anchor_or_solana_programs"]
    assert body["blockchainSecurityProfile"] == "solana_security_beginner"
    assert body["preferredFormats"] == ["research_labs"]
    assert body["securityLearningAttempt"] == "lightly"
    assert body["studyTechniques"] == ["writeups_or_case_studies"]
    assert body["difficultAreas"] == ["real_hack_examples"]
    assert body["practiceSignals"] == ["real_cases"]


async def test_onboarding_responses_does_not_require_wallet(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload["betaIntent"] = "not_now"
    payload.pop("contactName")
    payload.pop("preferredContactChannel")
    payload.pop("contact")

    response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json=payload,
    )

    assert response.status_code == 201
    created = response.json()["data"]
    assert created["walletAddress"] is None
    assert created["userId"] is None
    assert created["completed"] is True


async def test_onboarding_responses_requires_contact_when_beta_intent_active(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload.pop("contact")

    response = await seeded_client.post("/api/v1/onboarding/responses", json=payload)

    assert response.status_code == 422
    assert "contact" in response.json()["error"]["message"]


async def test_onboarding_responses_rejects_exclusive_no_experience(
    seeded_client: AsyncClient,
) -> None:
    payload = _v2_payload()
    payload["realExperience"] = ["not_built_anything", "rust_experience"]

    response = await seeded_client.post("/api/v1/onboarding/responses", json=payload)

    assert response.status_code == 422
    assert "mutually exclusive" in response.json()["error"]["message"]


async def test_admin_can_list_onboarding_responses(seeded_client: AsyncClient) -> None:
    payload = _v2_payload()
    create_response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json=payload,
    )
    assert create_response.status_code == 201

    response = await seeded_client.get(
        "/api/v1/onboarding/responses"
        "?profile=solana_developer"
        "&preferredFormat=research_labs"
        "&studyTechnique=official_docs"
        "&difficultArea=hands_on_practice"
        "&securityRelevanceMin=5"
        "&securityRelevanceMax=5"
        "&betaIntent=try_this_week",
        headers=await _admin_headers(seeded_client),
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["profile"] == "solana_developer"


async def test_admin_can_export_onboarding_responses_csv(seeded_client: AsyncClient) -> None:
    create_response = await seeded_client.post(
        "/api/v1/onboarding/responses",
        json=_v2_payload(),
    )
    assert create_response.status_code == 201

    response = await seeded_client.get(
        "/api/v1/onboarding/responses/export.csv?profile=solana_developer",
        headers=await _admin_headers(seeded_client),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "profile,realExperience" in response.text
    assert "solana_developer,built_simple_project;rust_experience" in response.text
