from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OnboardingProfile(StrEnum):
    SOLANA_DEVELOPER = "solana_developer"
    WEB3_DEVELOPER_NEW_TO_SOLANA = "web3_developer_new_to_solana"
    BACKEND_OR_RUST_DEVELOPER = "backend_or_rust_developer"
    STUDENT_OR_JUNIOR_BUILDER = "student_or_junior_builder"
    SECURITY_RESEARCHER_OR_AUDITOR = "security_researcher_or_auditor"
    COMMUNITY_BOOTCAMP_OR_TEAM = "community_bootcamp_or_team"


class RealExperience(StrEnum):
    NOT_BUILT_ANYTHING = "not_built_anything"
    BUILT_SIMPLE_PROJECT = "built_simple_project"
    WORKED_ANCHOR_OR_SOLANA_PROGRAMS = "worked_anchor_or_solana_programs"
    RUST_EXPERIENCE = "rust_experience"
    JOINED_HACKATHONS = "joined_hackathons"
    CONTRIBUTED_REAL_PROJECTS = "contributed_real_projects"


class BlockchainSecurityProfile(StrEnum):
    NO_SECURITY_BACKGROUND = "no_security_background"
    WEB2_SECURITY_BASICS = "web2_security_basics"
    WEB3_SECURITY_BASICS = "web3_security_basics"
    SOLANA_SECURITY_BEGINNER = "solana_security_beginner"
    CTF_OR_AUDIT_LEARNING = "ctf_or_audit_learning"
    PROFESSIONAL_AUDITOR_RESEARCHER = "professional_auditor_researcher"


class PreferredFormat(StrEnum):
    GUIDED_MODULES = "guided_modules"
    RESEARCH_LABS = "research_labs"
    AUDIT_ENVIRONMENTS = "audit_environments"
    SCORED_CHALLENGES = "scored_challenges"
    MENTOR_FEEDBACK = "mentor_feedback"
    FINAL_REPORT_OR_CERTIFICATE = "final_report_or_certificate"


class SecurityLearningAttempt(StrEnum):
    ACTIVE = "active"
    LIGHTLY = "lightly"
    TRIED_AND_STOPPED = "tried_and_stopped"
    INTERESTED_NOT_STARTED = "interested_not_started"
    NOT_PRIORITY = "not_priority"


class StudyTechnique(StrEnum):
    OFFICIAL_DOCS = "official_docs"
    SMALL_PROJECTS = "small_projects"
    VIDEOS_OR_WORKSHOPS = "videos_or_workshops"
    AI_ASSISTED = "ai_assisted"
    WRITEUPS_OR_CASE_STUDIES = "writeups_or_case_studies"
    CTFS_OR_CHALLENGES = "ctfs_or_challenges"
    MENTOR_OR_PEER_FEEDBACK = "mentor_or_peer_feedback"


class DifficultArea(StrEnum):
    SOLANA_PROGRAMS_AND_ACCOUNTS = "solana_programs_and_accounts"
    RUST_ANCHOR_BASICS = "rust_anchor_basics"
    SECURITY_MINDSET = "security_mindset"
    REAL_HACK_EXAMPLES = "real_hack_examples"
    HANDS_ON_PRACTICE = "hands_on_practice"
    TRANSACTIONS_WALLETS_PERMISSIONS = "transactions_wallets_permissions"
    EXPLAINING_FINDINGS = "explaining_findings"


class PracticeSignal(StrEnum):
    EXECUTE_EXPLOIT = "execute_exploit"
    SEE_STATE_CHANGES = "see_state_changes"
    VALIDATION_CHECKS = "validation_checks"
    REAL_CASES = "real_cases"
    FEEDBACK_OR_EXPLANATION = "feedback_or_explanation"
    FINAL_REPORT = "final_report"


class BetaIntent(StrEnum):
    TRY_THIS_WEEK = "try_this_week"
    TRY_LATER = "try_later"
    MAYBE = "maybe"
    NOT_NOW = "not_now"


class PreferredContactChannel(StrEnum):
    EMAIL = "email"
    TELEGRAM = "telegram"


def _split_legacy_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _parse_legacy_kv_blob(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    parsed: dict[str, str] = {}
    for part in value.split(";"):
        key, separator, raw_value = part.partition("=")
        if separator and key.strip() and raw_value.strip():
            parsed[key.strip()] = raw_value.strip()
    return parsed


def _parse_security_relevance(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip()
    if "/" in raw:
        raw = raw.split("/", 1)[0].strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_legacy_additional_notes(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    parsed: dict[str, str] = {}
    for line in value.splitlines():
        key, separator, raw_value = line.partition("=")
        if separator and key.strip() and raw_value.strip():
            parsed[key.strip()] = raw_value.strip()
    return parsed


LEGACY_STUDY_TECHNIQUES = {
    "audit_reports": "writeups_or_case_studies",
    "mentorship": "mentor_or_peer_feedback",
    "mentor": "mentor_or_peer_feedback",
    "mentor_feedback": "mentor_or_peer_feedback",
    "ai_tools": "ai_assisted",
    "ai": "ai_assisted",
    "docs": "official_docs",
    "documentation": "official_docs",
    "workshops": "videos_or_workshops",
    "videos": "videos_or_workshops",
    "youtube": "videos_or_workshops",
    "ctfs": "ctfs_or_challenges",
    "no_clear_path": "official_docs",
}

LEGACY_SECURITY_PROFILES = {
    "almost_none": "no_security_background",
    "joined_ctfs": "ctf_or_audit_learning",
    "ctfs": "ctf_or_audit_learning",
    "audit_learning": "ctf_or_audit_learning",
    "none": "no_security_background",
    "read_writeups_or_audit_reports": "solana_security_beginner",
    "reviewed_code_or_found_bugs": "web2_security_basics",
    "works_or_wants_auditing": "professional_auditor_researcher",
}

LEGACY_SECURITY_ATTEMPTS = {
    "almost_none": "interested_not_started",
    "joined_ctfs": "active",
    "read_writeups_or_audit_reports": "lightly",
    "reviewed_code_or_found_bugs": "lightly",
    "works_or_wants_auditing": "active",
}

LEGACY_PROFILES = {
    "protocol_or_technical_team": "backend_or_rust_developer",
    "educator_bootcamp_community": "community_bootcamp_or_team",
    "educator_bootcamp_or_community": "community_bootcamp_or_team",
    "community_bootcamp": "community_bootcamp_or_team",
    "security_researcher": "security_researcher_or_auditor",
    "other": "student_or_junior_builder",
}

LEGACY_REAL_EXPERIENCE = {
    "advanced": "contributed_real_projects",
    "learning_basics": "not_built_anything",
    "worked_with_anchor_or_programs": "worked_anchor_or_solana_programs",
}

LEGACY_PREFERRED_FORMATS = {
    "get_visible_proof_of_skill": "final_report_or_certificate",
    "learn_solana_security_through_practice": "guided_modules",
    "prepare_for_cohorts_or_audits": "audit_environments",
    "understand_real_vulnerabilities": "research_labs",
}

LEGACY_DIFFICULT_AREAS = {
    "get_visible_proof_of_skill": "explaining_findings",
    "learn_solana_security_through_practice": "hands_on_practice",
    "prepare_for_cohorts_or_audits": "hands_on_practice",
    "understand_real_vulnerabilities": "real_hack_examples",
}

LEGACY_PRACTICE_SIGNALS = {
    "get_visible_proof_of_skill": "final_report",
    "learn_solana_security_through_practice": "execute_exploit",
    "prepare_for_cohorts_or_audits": "validation_checks",
    "understand_real_vulnerabilities": "real_cases",
}


class OnboardingResponseCreateRequest(BaseModel):
    wallet_address: str | None = Field(default=None, alias="walletAddress", max_length=64)
    schema_version: int = Field(default=2, alias="schemaVersion")
    step: str | None = Field(default=None, max_length=80)
    completed: bool = True

    profile: OnboardingProfile | None = None
    real_experience: list[RealExperience] | None = Field(default=None, alias="realExperience")
    blockchain_security_profile: BlockchainSecurityProfile | None = Field(
        default=None,
        alias="blockchainSecurityProfile",
    )
    preferred_formats: list[PreferredFormat] | None = Field(default=None, alias="preferredFormats")
    security_learning_attempt: SecurityLearningAttempt | None = Field(
        default=None,
        alias="securityLearningAttempt",
    )
    study_techniques: list[StudyTechnique] | None = Field(default=None, alias="studyTechniques")
    difficult_areas: list[DifficultArea] | None = Field(default=None, alias="difficultAreas")
    hardest_practice_step: str | None = Field(
        default=None,
        alias="hardestPracticeStep",
        min_length=10,
        max_length=600,
    )
    practice_signals: list[PracticeSignal] | None = Field(default=None, alias="practiceSignals")
    security_relevance: int | None = Field(default=None, alias="securityRelevance", ge=1, le=5)
    beta_intent: BetaIntent | None = Field(default=None, alias="betaIntent")
    contact_name: str | None = Field(default=None, alias="contactName", max_length=160)
    preferred_contact_channel: PreferredContactChannel | None = Field(
        default=None,
        alias="preferredContactChannel",
    )
    contact: str | None = Field(default=None, max_length=255)
    source: str = Field(default="landing_onboarding", max_length=40)
    utm_source: str | None = Field(default=None, alias="utmSource", max_length=120)
    utm_medium: str | None = Field(default=None, alias="utmMedium", max_length=120)
    utm_campaign: str | None = Field(default=None, alias="utmCampaign", max_length=120)
    status: str = Field(default="submitted", max_length=40)

    responses: dict[str, Any] | list[Any] | None = None
    question_id: str | None = Field(default=None, alias="questionId", max_length=120)
    question_text: str | None = Field(default=None, alias="questionText", max_length=500)
    answer: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if normalized.get("responses") is not None or normalized.get("questionId") is not None:
            return normalized

        future_labs = _parse_legacy_kv_blob(normalized.get("futureLabsInterest"))
        notes = _parse_legacy_additional_notes(normalized.get("additionalNotes"))

        normalized.setdefault("contactName", normalized.get("name"))
        if normalized.get("profile") in LEGACY_PROFILES:
            normalized["profile"] = LEGACY_PROFILES[normalized["profile"]]

        if "realExperience" not in normalized:
            legacy_experience = future_labs.get("experience") or normalized.get("solanaLevel")
            values = _split_legacy_values(legacy_experience)
            values = [LEGACY_REAL_EXPERIENCE.get(value, value) for value in values]
            if values:
                normalized["realExperience"] = values

        if "blockchainSecurityProfile" not in normalized:
            legacy_profile = future_labs.get("security_profile") or normalized.get(
                "securityExperience"
            )
            mapped = LEGACY_SECURITY_PROFILES.get(str(legacy_profile), legacy_profile)
            if mapped:
                normalized["blockchainSecurityProfile"] = mapped

        if "preferredFormats" not in normalized:
            values = _split_legacy_values(future_labs.get("formats"))
            if not values:
                values = _split_legacy_values(normalized.get("mainGoal"))
            values = [LEGACY_PREFERRED_FORMATS.get(value, value) for value in values]
            if values:
                normalized["preferredFormats"] = values

        if "securityLearningAttempt" not in normalized and future_labs.get("security_attempt"):
            normalized["securityLearningAttempt"] = future_labs["security_attempt"]
        if "securityLearningAttempt" not in normalized:
            legacy_attempt = LEGACY_SECURITY_ATTEMPTS.get(
                str(normalized.get("securityExperience"))
            )
            if legacy_attempt:
                normalized["securityLearningAttempt"] = legacy_attempt

        if "studyTechniques" not in normalized:
            values = _split_legacy_values(future_labs.get("study"))
            if not values:
                values = _split_legacy_values(normalized.get("currentLearningSources"))
            mapped_values = [LEGACY_STUDY_TECHNIQUES.get(value, value) for value in values]
            if mapped_values:
                normalized["studyTechniques"] = mapped_values

        if "difficultAreas" not in normalized:
            values = _split_legacy_values(future_labs.get("areas"))
            if not values:
                values = [
                    LEGACY_DIFFICULT_AREAS[value]
                    for value in _split_legacy_values(normalized.get("mainGoal"))
                    if value in LEGACY_DIFFICULT_AREAS
                ]
            if values:
                normalized["difficultAreas"] = values

        if "hardestPracticeStep" not in normalized:
            hardest = notes.get("hardest") or normalized.get("additionalNotes")
            if hardest:
                normalized["hardestPracticeStep"] = hardest

        if "practiceSignals" not in normalized:
            values = _split_legacy_values(future_labs.get("practice"))
            if not values:
                values = [
                    LEGACY_PRACTICE_SIGNALS[value]
                    for value in _split_legacy_values(normalized.get("mainGoal"))
                    if value in LEGACY_PRACTICE_SIGNALS
                ]
            if values:
                normalized["practiceSignals"] = values

        if "securityRelevance" not in normalized:
            relevance = _parse_security_relevance(
                future_labs.get("security_relevance")
                or notes.get("security_relevance")
                or normalized.get("guidedLabUsefulness")
            )
            if relevance is not None:
                normalized["securityRelevance"] = relevance

        return normalized

    @field_validator(
        "wallet_address",
        "step",
        "source",
        "contact_name",
        "contact",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "status",
        "question_id",
        "question_text",
        mode="before",
    )
    @classmethod
    def trim_optional_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = " ".join(value.strip().split())
            return stripped or None
        return value

    @field_validator("hardest_practice_step", mode="before")
    @classmethod
    def trim_long_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator(
        "real_experience",
        "preferred_formats",
        "study_techniques",
        "difficult_areas",
        "practice_signals",
        mode="after",
    )
    @classmethod
    def dedupe_multi_select(cls, value: list[StrEnum] | None) -> list[StrEnum] | None:
        if value is None:
            return None
        deduped = list(dict.fromkeys(value))
        if not deduped:
            raise ValueError("must contain at least one value")
        return deduped

    @model_validator(mode="after")
    def validate_contract(self) -> OnboardingResponseCreateRequest:
        if self.responses is not None or self.question_id is not None:
            return self

        missing = [
            field
            for field, value in {
                "profile": self.profile,
                "realExperience": self.real_experience,
                "blockchainSecurityProfile": self.blockchain_security_profile,
                "preferredFormats": self.preferred_formats,
                "securityLearningAttempt": self.security_learning_attempt,
                "studyTechniques": self.study_techniques,
                "difficultAreas": self.difficult_areas,
                "hardestPracticeStep": self.hardest_practice_step,
                "practiceSignals": self.practice_signals,
                "securityRelevance": self.security_relevance,
                "betaIntent": self.beta_intent,
            }.items()
            if value is None
        ]
        if missing:
            raise ValueError(f"Missing required onboarding fields: {', '.join(missing)}")

        assert self.real_experience is not None
        if (
            RealExperience.NOT_BUILT_ANYTHING in self.real_experience
            and len(self.real_experience) > 1
        ):
            raise ValueError("not_built_anything is mutually exclusive")

        if self.beta_intent != BetaIntent.NOT_NOW:
            contact_missing = [
                field
                for field, value in {
                    "contactName": self.contact_name,
                    "preferredContactChannel": self.preferred_contact_channel,
                    "contact": self.contact,
                }.items()
                if value is None
            ]
            if contact_missing:
                raise ValueError(
                    "Contact fields are required unless betaIntent is not_now: "
                    + ", ".join(contact_missing)
                )
        return self

    @property
    def is_v2(self) -> bool:
        return self.responses is None and self.question_id is None

    def normalized_responses(self) -> dict[str, Any] | list[Any]:
        if self.responses is not None:
            return self.responses
        if self.question_id is not None:
            return {
                "questionId": self.question_id,
                "questionText": self.question_text,
                "answer": self.answer,
            }
        return self.v2_responses()

    def v2_responses(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "realExperience": self.real_experience or [],
            "blockchainSecurityProfile": self.blockchain_security_profile,
            "preferredFormats": self.preferred_formats or [],
            "securityLearningAttempt": self.security_learning_attempt,
            "studyTechniques": self.study_techniques or [],
            "difficultAreas": self.difficult_areas or [],
            "hardestPracticeStep": self.hardest_practice_step,
            "practiceSignals": self.practice_signals or [],
            "securityRelevance": self.security_relevance,
            "betaIntent": self.beta_intent,
            "contactName": self.contact_name,
            "preferredContactChannel": self.preferred_contact_channel,
            "contact": self.contact,
            "source": self.source,
            "utmSource": self.utm_source,
            "utmMedium": self.utm_medium,
            "utmCampaign": self.utm_campaign,
        }

    def analytics_dimensions(self) -> dict[str, Any]:
        if not self.is_v2:
            return {"schemaVersion": self.schema_version}
        return {
            "schemaVersion": self.schema_version,
            "profile": self.profile,
            "blockchainSecurityProfile": self.blockchain_security_profile,
            "securityLearningAttempt": self.security_learning_attempt,
            "securityRelevance": self.security_relevance,
            "betaIntent": self.beta_intent,
            "realExperienceCount": len(self.real_experience or []),
            "preferredFormatsCount": len(self.preferred_formats or []),
            "studyTechniquesCount": len(self.study_techniques or []),
            "difficultAreasCount": len(self.difficult_areas or []),
            "practiceSignalsCount": len(self.practice_signals or []),
        }


class OnboardingResponseData(BaseModel):
    id: str
    wallet_address: str | None = Field(alias="walletAddress")
    user_id: str | None = Field(alias="userId")
    schema_version: int = Field(alias="schemaVersion")
    step: str | None
    source: str
    completed: bool
    status: str
    profile: str | None
    real_experience: list[str] = Field(alias="realExperience")
    blockchain_security_profile: str | None = Field(alias="blockchainSecurityProfile")
    preferred_formats: list[str] = Field(alias="preferredFormats")
    security_learning_attempt: str | None = Field(alias="securityLearningAttempt")
    study_techniques: list[str] = Field(alias="studyTechniques")
    difficult_areas: list[str] = Field(alias="difficultAreas")
    hardest_practice_step: str | None = Field(alias="hardestPracticeStep")
    practice_signals: list[str] = Field(alias="practiceSignals")
    security_relevance: int | None = Field(alias="securityRelevance")
    beta_intent: str | None = Field(alias="betaIntent")
    contact_name: str | None = Field(alias="contactName")
    preferred_contact_channel: str | None = Field(alias="preferredContactChannel")
    contact: str | None
    utm_source: str | None = Field(alias="utmSource")
    utm_medium: str | None = Field(alias="utmMedium")
    utm_campaign: str | None = Field(alias="utmCampaign")
    responses: dict[str, Any] | list[Any]
    metadata: dict[str, Any]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class OnboardingAPIResponse(BaseModel):
    success: bool = True
    data: Any
    error: Any = None
