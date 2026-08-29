from unittest.mock import MagicMock, patch

import inspect

from main import AGENT_LIMITS, JobHunterCrew


def test_agent_limits_constants():
    assert AGENT_LIMITS["allow_delegation"] is False
    assert AGENT_LIMITS["max_iter"] >= 1
    assert AGENT_LIMITS["max_rpm"] >= 1
    assert AGENT_LIMITS["max_execution_time"] >= 60


@patch("main.Agent")
def test_job_search_agent_applies_limits(mock_agent_cls):
    mock_agent_cls.return_value = MagicMock()
    JobHunterCrew().job_search_agent()
    # CrewBase may construct other agents during init; find the search agent call.
    search_calls = [
        c
        for c in mock_agent_cls.call_args_list
        if c.kwargs.get("tools")
    ]
    assert search_calls
    kwargs = search_calls[0].kwargs
    assert kwargs["allow_delegation"] is False
    assert kwargs["max_iter"] == 4
    assert kwargs["respect_context_window"] is True
    assert kwargs["llm"] is not None


@patch("main.Agent")
def test_all_agents_apply_limits(mock_agent_cls):
    mock_agent_cls.return_value = MagicMock()
    crew = JobHunterCrew()
    for factory in (
        crew.job_search_agent,
        crew.job_matching_agent,
        crew.resume_optimization_agent,
        crew.company_research_agent,
        crew.interview_prep_agent,
    ):
        factory()
    assert mock_agent_cls.call_count == 5
    for call in mock_agent_cls.call_args_list:
        assert call.kwargs["allow_delegation"] is False


def test_crew_method_specifies_sequential_process():
    source = inspect.getsource(JobHunterCrew.crew)
    assert "process=Process.sequential" in source
