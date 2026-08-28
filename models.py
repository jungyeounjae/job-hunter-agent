from typing import List, Literal
from pydantic import BaseModel
from datetime import date


class Job(BaseModel):

    job_title: str
    company_name: str
    job_location: str
    is_remote_friendly: bool | None = None
    employment_type: str | None = None
    compensation: str | None = None
    job_posting_url: str
    job_summary: str

    key_qualifications: List[str] | None = None
    job_responsibilities: List[str] | None = None
    date_listed: date | None = None
    required_technologies: List[str] | None = None
    core_keywords: List[str] | None = None

    role_seniority_level: str | None = None
    years_of_experience_required: str | None = None
    minimum_education: str | None = None
    job_benefits: List[str] | None = None
    includes_equity: bool | None = None
    offers_visa_sponsorship: bool | None = None
    # Overseas applicant filters (None = 미확인, not "no requirement")
    overseas_applicable: bool | None = None
    visa_support: bool | None = None
    japanese_level: str | None = None
    foreign_hire_track_record: bool | None = None
    hiring_company_size: str | None = None
    hiring_industry: str | None = None
    source_listing_url: str | None = None
    full_raw_job_description: str | None = None


class JobList(BaseModel):
    jobs: List[Job]


class LabeledJob(BaseModel):
    id: str
    label: Literal["match", "no_match"]
    rationale_ko: str = ""
    job: Job


class RankedJob(BaseModel):
    job: Job
    match_score: int
    reason: str
    semantic_score: float | None = None
    url_verified: bool | None = None


class RankedJobList(BaseModel):
    ranked_jobs: List[RankedJob]


class ChosenJob(BaseModel):
    job: Job
    selected: bool
    reason: str


class LanguageSkill(BaseModel):
    code: str
    level: str


class FieldConfidence(BaseModel):
    field: str
    confidence: float


class ResumeProfile(BaseModel):
    headline_ko: str
    target_roles: list[str]
    seniority_level: str | None = None
    years_of_experience: float | None = None
    skills: list[str]
    languages: list[LanguageSkill]
    visa_status: str | None = None
    preferred_locations: list[str]
    search_queries_ja: list[str]
    search_queries_en: list[str]
    matching_document: str
    confidence: float
    field_confidence: list[FieldConfidence] = []
    parse_warnings: list[str]
    status: Literal["ok", "partial", "failed"]


class CompanyFactcheck(BaseModel):
    corporate_number: str | None
    gbiz_fields: dict
    risk_tags: list[str]
    summary_ko: str
    sources: list[str]
    status: Literal["verified", "public_unconfirmed", "error"]


class MvpRunResult(BaseModel):
    resume_profile: ResumeProfile | None = None
    ranked_jobs: list[RankedJob]
    chosen_job: ChosenJob
    factcheck: CompanyFactcheck
    used_fallback: bool
    used_raw_resume_fallback: bool = False