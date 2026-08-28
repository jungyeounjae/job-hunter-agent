from models import ChosenJob, CompanyFactcheck, Job, MvpRunResult, RankedJob, ResumeProfile, LanguageSkill, FieldConfidence


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


def test_company_factcheck_status_literal():
    fc = CompanyFactcheck(
        corporate_number="1234567890123",
        gbiz_fields={"name": "Example KK"},
        risk_tags=["소규모"],
        summary_ko="공공 데이터 확인됨",
        sources=["gBizINFO"],
        status="verified",
    )
    assert fc.status == "verified"


def test_mvp_run_result_shape():
    job = Job(
        job_title="PM",
        company_name="Acme",
        job_location="Osaka",
        job_posting_url="https://example.com/job/2",
        job_summary="Lead product",
    )
    chosen = ChosenJob(job=job, selected=True, reason="Best match")
    fc = CompanyFactcheck(
        corporate_number=None,
        gbiz_fields={},
        risk_tags=[],
        summary_ko="미확인",
        sources=[],
        status="public_unconfirmed",
    )
    result = MvpRunResult(
        ranked_jobs=[],
        chosen_job=chosen,
        factcheck=fc,
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
        factcheck=CompanyFactcheck(
            corporate_number=None,
            gbiz_fields={},
            risk_tags=[],
            summary_ko="x",
            sources=[],
            status="public_unconfirmed",
        ),
        used_fallback=False,
        used_raw_resume_fallback=True,
    )
    assert result.used_raw_resume_fallback is True
