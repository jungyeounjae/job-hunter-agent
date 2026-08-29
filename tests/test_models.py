from models import ChosenJob, Job, MvpRunResult, RankedJob, ResumeProfile, LanguageSkill, FieldConfidence


def test_ranked_job_accepts_semantic_fields():
    job = Job(
        job_title="Backend Engineer",
        company_name="Example KK",
        job_location="Tokyo",
        job_posting_url="https://example.com/job/1",
        job_summary="Build APIs",
    )
    ranked = RankedJob(
        job=job,
        match_score=4,
        reason="Good fit",
        semantic_score=0.82,
        url_verified=True,
    )
    assert ranked.semantic_score == 0.82
    assert ranked.url_verified is True


def test_mvp_run_result_shape():
    job = Job(
        job_title="PM",
        company_name="Acme",
        job_location="Osaka",
        job_posting_url="https://example.com/job/2",
        job_summary="Lead product",
    )
    chosen = ChosenJob(job=job, selected=True, reason="Best match")
    result = MvpRunResult(
        ranked_jobs=[],
        chosen_job=chosen,
        used_fallback=False,
    )
    assert result.used_fallback is False


def test_resume_profile_ok_status():
    profile = ResumeProfile(
        headline_ko="풀스택 3년, 일본어 네이티브",
        target_roles=["풀스택 엔지니어"],
        seniority_level="Mid",
        years_of_experience=3.0,
        skills=["Java", "GCP"],
        languages=[
            LanguageSkill(code="ko", level="native"),
            LanguageSkill(code="ja", level="native"),
        ],
        visa_status="취업비자",
        preferred_locations=["Tokyo"],
        search_queries_ja=["フルスタック エンジニア 東京"],
        search_queries_en=["full stack engineer Tokyo"],
        matching_document="풀스택 엔지니어, Java/GCP...",
        confidence=0.85,
        field_confidence=[FieldConfidence(field="skills", confidence=0.9)],
        parse_warnings=[],
        status="ok",
    )
    assert profile.status == "ok"
    assert profile.search_queries_ja[0].startswith("フル")


def test_mvp_run_result_includes_profile_fields():
    job = Job(
        job_title="Dev",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com",
        job_summary="x",
    )
    result = MvpRunResult(
        resume_profile=None,
        ranked_jobs=[],
        chosen_job=ChosenJob(job=job, selected=True, reason="ok"),
        used_fallback=False,
        used_raw_resume_fallback=True,
    )
    assert result.used_raw_resume_fallback is True


def test_job_overseas_fields_default_to_none():
    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com/job",
        job_summary="API role",
    )
    assert job.overseas_applicable is None
    assert job.visa_support is None
    assert job.japanese_level is None
    assert job.foreign_hire_track_record is None


def test_job_overseas_fields_accept_values():
    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com/job",
        job_summary="Remote OK for overseas applicants",
        overseas_applicable=True,
        visa_support=True,
        japanese_level="JLPT N2",
        foreign_hire_track_record=True,
    )
    assert job.overseas_applicable is True
    assert job.japanese_level == "JLPT N2"
