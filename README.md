# CareerTwin AI — Student Digital Twin & Counterfactual Career Coach

Hackathon demo that helps students inspect placement **readiness estimates**, simulate what-if changes, and generate a weekly plan through a real PLAN → ACT → OBSERVE → RE-PLAN agent.

**Important:** Placement percentages come from a logistic regression trained on **reproducible synthetic data**. They are coaching estimates, not validated real-world offer probabilities. The UI and API label this on every prediction.

## Stack

- Frontend: React 18, Vite, Tailwind CSS, Recharts
- Backend: FastAPI, SQLAlchemy, SQLite
- Model: scikit-learn `LogisticRegression` on synthetic campus-style records
- Agent: OpenAI-compatible tool calling, with a labelled deterministic fallback if `OPENAI_API_KEY` is missing

## Features

1. Digital twin (aptitude, English, technical, mocks, attendance, applications, internships, CGPA, projects)
2. Placement predictor with factor-level explanations and limitations
3. What-if simulator (for example +3 mock interviews and +10 aptitude)
4. AI career agent that **actually calls tools**
5. Agentic loop with persisted logs
6. SQLite memory for profiles, predictions, plans, progress, and agent traces
7. Human approval before a weekly plan can be activated
8. Guardrails (range checks, missing-data warnings, refusal of unverified achievement spikes / forged-offer language)
9. Evaluation suite (≥12 cases) plus held-out accuracy, precision, recall, and F1

### Agent tools

- `get_student_profile()`
- `run_placement_prediction()`
- `simulate_what_if()`
- `save_weekly_plan()` (always stores `pending_approval`)
- `update_student_progress()`

## Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Optional in `.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

If the key is absent, the agent still runs tools in a deterministic PLAN/ACT/OBSERVE/RE-PLAN loop and labels the mode as `deterministic_fallback`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://127.0.0.1:8000.

## Demo path

1. Pick a sample twin (Aanya, Rohan, Meera, Dev, or Sara).
2. Overview → inspect scores and log a job application.
3. Predictor → run the model and read factor contributions.
4. What-if → keep +3 mocks and +10 aptitude, compare estimates.
5. Skills → try a modest progress update; try internships `5` on a student with `0` to see the guardrail.
6. AI assistant → generate a weekly plan.
7. Weekly planner → Approve, then Activate. Activating before approval returns an API error.
8. Agent log → confirm real tool payloads.
9. Evaluation → run the 12-case report.

## API (selected)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness + whether an LLM key is configured |
| GET | `/api/students` | Sample twins |
| POST | `/api/students/{id}/predict` | Persist a baseline estimate |
| POST | `/api/students/{id}/what-if` | Counterfactual comparison |
| POST | `/api/students/{id}/agent` | Full agent loop |
| POST | `/api/plans/{id}/approve` | Human approval |
| POST | `/api/plans/{id}/activate` | Activate only if approved |
| GET | `/api/evaluation` | Metrics + test cases |

## Model notes

Training data is generated with a fixed seed (`42`) and a known logit process. Held-out classification metrics describe **synthetic labels only**. Do not present them as campus placement accuracy.
