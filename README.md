# job-hunter-agent

CrewAI-based agent that searches jobs, matches your profile, and prepares application materials.

## Setup

```bash
uv sync
cp .env.example .env          # add your API keys
cp knowledge/resume.txt.example knowledge/resume.txt   # add your resume
```

## Run

```bash
uv run python main.py
```

Generated files are written to `output/` (local only, not committed).
