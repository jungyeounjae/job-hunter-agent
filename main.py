import os

import dotenv

dotenv.load_dotenv()

from crewai import Crew, Agent, Task, Process, LLM
from crewai.project import CrewBase, task, agent, crew
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from models import JobList, RankedJobList, ChosenJob
from tools import web_search_tool

resume_knowledge = TextFileKnowledgeSource(
    file_paths=[
        "resume.txt",
    ]
)

# Sequential pipeline: explicit caps to avoid runaway tool loops / delegation.
AGENT_LIMITS = {
    "allow_delegation": False,
    "max_iter": 15,
    "max_rpm": 10,
    "max_execution_time": 300,
}


from llm_config import crew_llm_model_id


def default_crew_llm() -> LLM:
    return LLM(model=crew_llm_model_id(), api_key=os.getenv("OPENAI_API_KEY"))


@CrewBase
class JobHunterCrew:

    @agent
    def job_search_agent(self):
        return Agent(
            config=self.agents_config["job_search_agent"],
            tools=[web_search_tool],
            llm=default_crew_llm(),
            allow_delegation=False,
            max_iter=4,
            max_rpm=10,
            max_execution_time=300,
            respect_context_window=True,
        )

    @agent
    def job_matching_agent(self):
        return Agent(
            config=self.agents_config["job_matching_agent"],
            knowledge_sources=[resume_knowledge],
            llm=default_crew_llm(),
            **AGENT_LIMITS,
        )

    @agent
    def resume_optimization_agent(self):
        return Agent(
            config=self.agents_config["resume_optimization_agent"],
            knowledge_sources=[resume_knowledge],
            llm=default_crew_llm(),
            **AGENT_LIMITS,
        )

    @agent
    def company_research_agent(self):
        return Agent(
            config=self.agents_config["company_research_agent"],
            knowledge_sources=[resume_knowledge],
            tools=[web_search_tool],
            llm=default_crew_llm(),
            **AGENT_LIMITS,
        )

    @agent
    def interview_prep_agent(self):
        return Agent(
            config=self.agents_config["interview_prep_agent"],
            knowledge_sources=[resume_knowledge],
            llm=default_crew_llm(),
            **AGENT_LIMITS,
        )

    @task
    def job_extraction_task(self):
        return Task(
            config=self.tasks_config["job_extraction_task"],
            output_pydantic=JobList,
        )

    @task
    def job_matching_task(self):
        return Task(
            config=self.tasks_config["job_matching_task"],
            output_pydantic=RankedJobList,
        )

    @task
    def job_selection_task(self):
        return Task(
            config=self.tasks_config["job_selection_task"],
            output_pydantic=ChosenJob,
        )

    @task
    def resume_rewriting_task(self):
        return Task(
            config=self.tasks_config["resume_rewriting_task"],
            context=[
                self.job_selection_task(),
            ],
        )

    @task
    def company_research_task(self):
        return Task(
            config=self.tasks_config["company_research_task"],
            context=[
                self.job_selection_task(),
            ],
        )

    @task
    def interview_prep_task(self):
        return Task(
            config=self.tasks_config["interview_prep_task"],
            context=[
                self.job_selection_task(),
                self.resume_rewriting_task(),
                self.company_research_task(),
            ],
        )

    @crew
    def crew(self):
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            process=Process.sequential,
        )


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Job Hunter Agent CLI")
    parser.add_argument(
        "--mode",
        choices=["mvp", "full"],
        default="mvp",
        help="mvp: R→E (same as Streamlit). full: legacy 6-step Crew pipeline.",
    )
    parser.add_argument(
        "--prefecture",
        default="東京都",
        help="Target prefecture for mvp mode (default: 東京都)",
    )
    args = parser.parse_args()

    if args.mode == "mvp":
        from crew_runner import run_mvp

        resume_path = Path("knowledge/resume.txt")
        if not resume_path.exists():
            raise SystemExit(
                "knowledge/resume.txt not found. "
                "Copy knowledge/resume.txt.example and fill in your resume."
            )
        resume_text = resume_path.read_text(encoding="utf-8")

        def _cli_progress(message: str) -> None:
            print(f"→ {message}", flush=True)

        result = run_mvp(
            resume_text,
            args.prefecture,
            on_progress=_cli_progress,
        )
        print(f"\n선정: {result.chosen_job.job.company_name} — {result.chosen_job.job.job_title}")
        print(f"이유: {result.chosen_job.reason}")
        print(f"링크: {result.chosen_job.job.job_posting_url}")
        if result.run_artifact_dir:
            print(f"아티팩트: {result.run_artifact_dir}")
    else:
        JobHunterCrew().crew().kickoff(
            inputs={
                "level": "Senior",
                "position": "AI Agents Developer",
                "location": args.prefecture,
                "search_queries": "AI エージェント 東京",
            }
        )
