# Clara AI — Zero-Cost Automation Pipeline

> **Demo Call → Retell Agent Draft → Onboarding Updates → Agent Revision**

An end-to-end automation pipeline that transforms raw call transcripts into deployable Retell AI voice agent configurations. Built for service trade companies (fire protection, HVAC, electrical, security).

---

## Architecture and Data Flow

```
data/demo/demo_NNN.txt          data/onboarding/onboarding_NNN.txt
         │                                      │
         ▼                                      ▼
  ┌─────────────┐                      ┌─────────────────┐
  │  Pipeline A │                      │   Pipeline B    │
  │  (Demo →    │                      │  (Onboarding →  │
  │   v1 Agent) │                      │   v2 Agent)     │
  └──────┬──────┘                      └────────┬────────┘
         │                                      │
         ▼                                      ▼
  ┌─────────────────────────────────────────────────────────┐
  │  scripts/extract_memo.py                                │
  │  • Rule-based extraction (regex + heuristics)          │
  │  • Optional LLM enhancement (Groq free tier / Ollama)  │
  │  • Produces: Account Memo JSON                         │
  └─────────────────────────────────────────────────────────┘
         │                                      │
         ▼                                      ▼
  ┌─────────────────┐                  ┌────────────────────┐
  │ generate_agent  │                  │  update_agent.py   │
  │ _spec.py        │                  │  • Merge v1 + new  │
  │ • System prompt │                  │  • Detect conflicts│
  │ • Transfer rules│                  │  • Generate diff   │
  │ • Fallback proto│                  └────────┬───────────┘
  └────────┬────────┘                           │
           │                                    ▼
           ▼                          ┌──────────────────────┐
  outputs/accounts/<id>/v1/           │ generate_agent       │
    memo.json                         │ _spec.py (v2)        │
    agent_spec.json                   └────────┬─────────────┘
                                               │
                                               ▼
                                     outputs/accounts/<id>/v2/
                                       memo.json
                                       agent_spec.json
                                     outputs/accounts/<id>/
                                       changelog.md
                                       diff.json
```

### Key Design Principles

- **Separation of concerns**: Demo-derived assumptions (v1) are clearly separate from onboarding-confirmed rules (v2).
- **No hallucination**: Missing fields are flagged as `questions_or_unknowns`, never invented.
- **Idempotent**: Running the same pipeline twice produces identical output.
- **Zero-cost**: Works fully offline with rule-based extraction; optionally enhanced with Groq free tier or local Ollama.

---

## Directory Structure

```
claraAI/
├── README.md
├── requirements.txt              # Python deps (groq, python-dotenv)
├── docker-compose.yml            # n8n local setup
├── .gitignore
│
├── scripts/                      # Core Python pipeline scripts
│   ├── __init__.py
│   ├── utils.py                  # Shared utilities (I/O, diff, logging)
│   ├── llm_client.py             # LLM backend abstraction
│   ├── extract_memo.py           # Extract Account Memo from transcript
│   ├── generate_agent_spec.py    # Generate Retell Agent Spec
│   ├── update_agent.py           # Merge onboarding updates, generate changelog
│   ├── pipeline_a.py             # Pipeline A: demo → v1
│   ├── pipeline_b.py             # Pipeline B: onboarding → v2
│   └── batch_run.py              # Run all 10 files end-to-end
│
├── workflows/
│   └── n8n_workflow.json         # n8n workflow export (importable)
│
├── data/
│   ├── demo/                     # Demo call transcripts (demo_001.txt … demo_005.txt)
│   └── onboarding/               # Onboarding transcripts (onboarding_001.txt … _005.txt)
│
├── outputs/
│   ├── batch_summary.json        # Summary of the most recent batch run
│   └── accounts/
│       └── account_NNN/
│           ├── v1/
│           │   ├── memo.json         # v1 Account Memo (from demo)
│           │   └── agent_spec.json   # v1 Retell Agent Spec
│           ├── v2/
│           │   ├── memo.json         # v2 Account Memo (updated after onboarding)
│           │   └── agent_spec.json   # v2 Retell Agent Spec
│           ├── changelog.md          # Human-readable diff (v1 → v2)
│           └── diff.json             # Machine-readable diff
│
└── tests/
    └── test_pipeline.py          # 68 pytest tests
```

---

## How to Run Locally

### Prerequisites

- Python 3.10+
- (Optional) Groq API key — [free at console.groq.com](https://console.groq.com)
- (Optional) Docker — for running n8n

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure (optional)

Create a `.env` file (or export env vars):

```bash
# LLM backend — choose one:
# Option A: Rule-based only (zero-cost, always works)
LLM_BACKEND=rule_based

# Option B: Groq free tier (better extraction quality)
LLM_BACKEND=groq
GROQ_API_KEY=your_groq_api_key_here

# Option C: Local Ollama (zero-cost, requires Ollama installed)
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Optional: task tracker (Asana free tier)
ASANA_API_TOKEN=your_asana_token
ASANA_PROJECT_ID=your_project_gid
```

### 3. Run the full batch (all 5 accounts, both pipelines)

```bash
# With rule-based extraction (no API key needed)
python scripts/batch_run.py --no-llm

# With LLM enhancement (Groq or Ollama — reads LLM_BACKEND env var)
python scripts/batch_run.py
```

### 4. Run a single account

**Pipeline A (demo → v1):**
```bash
python scripts/pipeline_a.py data/demo/demo_001.txt --account-id account_001
```

**Pipeline B (onboarding → v2):**
```bash
python scripts/pipeline_b.py data/onboarding/onboarding_001.txt --account-id account_001
```

### 5. Run tests

```bash
python -m pytest tests/ -v
```

---

## How to Plug In Your Own Dataset

1. Place your transcript files in:
   - `data/demo/demo_NNN.txt` (demo calls)
   - `data/onboarding/onboarding_NNN.txt` (onboarding calls)

   Files are matched by numeric suffix (e.g., `demo_006.txt` pairs with `onboarding_006.txt`).

2. Run the batch:
   ```bash
   python scripts/batch_run.py
   ```

3. Outputs are written to `outputs/accounts/account_NNN/`.

**Transcript format requirements:**
- Plain text files
- Ideally include a header: `Account ID: account_NNN`
- Standard conversation format works best (Name: text)
- No specific format required — the extraction engine handles messy transcripts

---

## Retell Setup Instructions

### Option A: API (if free tier allows)

1. Create an account at [retell.ai](https://www.retell.ai)
2. Navigate to Settings → API Keys
3. Copy your API key
4. The pipeline generates a `retell_import_instructions` field in every `agent_spec.json` with step-by-step guidance

### Option B: Manual import (recommended for demo)

Each `agent_spec.json` includes `retell_import_instructions`:

1. Log in to [app.retell.ai](https://app.retell.ai)
2. Go to **Agents** → **Create New Agent**
3. Set Agent Name to `agent_name` from `agent_spec.json`
4. Select voice from Voice Library (see `voice_style.voice_id`)
5. Paste the `system_prompt` field into the System Prompt text area
6. Configure transfer numbers from `call_transfer_protocol`
7. Save and test with a sample call

---

## n8n Setup

### Local (Docker)

```bash
docker-compose up -d
```

Then:
1. Open [http://localhost:5678](http://localhost:5678)
2. Login: admin / changeme
3. Go to **Workflows** → **Import from File**
4. Import `workflows/n8n_workflow.json`
5. Set credentials if using Asana task tracking
6. Activate the workflow

### Environment Variables for n8n

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | No | Groq API key (free tier) for LLM extraction |
| `OLLAMA_URL` | No | Local Ollama URL (default: `http://localhost:11434`) |
| `LLM_BACKEND` | No | Force backend: `groq`, `ollama`, or `rule_based` |
| `ASANA_API_TOKEN` | No | Asana personal access token for task creation |
| `ASANA_PROJECT_ID` | No | Asana project GID for task placement |

---

## Output Format Reference

### Account Memo JSON (`memo.json`)

| Field | Description |
|---|---|
| `account_id` | Unique account identifier |
| `company_name` | Company name |
| `business_hours` | `{days, start, end, timezone}` |
| `office_address` | Street address or null |
| `services_supported` | List of services |
| `emergency_definition` | List of trigger conditions |
| `emergency_routing_rules` | Primary/secondary numbers, timeout, fallback message |
| `non_emergency_routing_rules` | Action, callback promise, info to collect |
| `call_transfer_rules` | Business hours transfer config |
| `integration_constraints` | Software constraints (e.g., never mention ServiceTrade) |
| `after_hours_flow_summary` | Summary of after-hours call flow |
| `office_hours_flow_summary` | Summary of business hours call flow |
| `questions_or_unknowns` | Flagged missing/unclear fields |
| `notes` | Free-text notes |
| `version` | `v1` (demo) or `v2` (post-onboarding) |

### Retell Agent Spec (`agent_spec.json`)

| Field | Description |
|---|---|
| `agent_name` | Display name |
| `version` | `v1` or `v2` |
| `voice_style` | Provider, voice ID, tone |
| `system_prompt` | Full conversation script for Clara |
| `key_variables` | Business hours, timezone, transfer numbers |
| `tool_invocation_placeholders` | Tool schemas (transfer_call, log_message, check_business_hours) |
| `call_transfer_protocol` | Business hours + emergency transfer config |
| `fallback_protocol` | What to do when all transfers fail |
| `retell_import_instructions` | Step-by-step manual import guide |

### Changelog (`changelog.md`)

Human-readable Markdown file showing every change from v1 → v2:
- All `CHANGED`, `ADDED`, `REMOVED` fields
- Conflict resolutions (when demo and onboarding disagree)
- Remaining open questions

---

## LLM Integration (Zero-Cost Options)

The pipeline supports three extraction modes:

### 1. Rule-based (default, always zero-cost)
Pure regex and heuristic extraction. Works on any machine without any API key.
```bash
python scripts/batch_run.py --no-llm
```

### 2. Groq API (free tier, recommended for production quality)
Groq provides a generous free tier with fast Llama 3 inference.
```bash
export GROQ_API_KEY=your_free_api_key
python scripts/batch_run.py
```
Free tier limits (as of 2024): ~14,400 requests/day on `llama3-8b-8192`.

### 3. Local Ollama (zero-cost, requires local hardware)
```bash
# Install Ollama: https://ollama.ai
ollama pull llama3
export LLM_BACKEND=ollama
python scripts/batch_run.py
```

The pipeline automatically falls back to rule-based if the configured LLM fails.

---

## Known Limitations

1. **Rule-based extraction is heuristic**: It works best with structured transcript format. Very messy or free-form audio-to-text transcripts may miss some fields.

2. **No real-time audio transcription**: The pipeline accepts text transcripts as input. For audio files, use a free transcription tool first (e.g., Whisper CLI, AssemblyAI free tier) and provide the resulting `.txt` file.

3. **Retell API not called directly**: The pipeline generates a compliant agent spec JSON but does not call Retell APIs, because Retell requires a paid plan for programmatic agent creation. The manual import path works on all tiers.

4. **Task tracker is optional**: Asana integration is included but optional. The pipeline works fully without it.

5. **Phone number extraction from demo calls**: Demo calls typically don't include specific phone numbers (these are confirmed at onboarding). v1 memos will have null phone numbers flagged in `questions_or_unknowns` — this is intentional and correct behavior.

---

## What I Would Improve with Production Access

1. **Real Retell API integration**: With a Retell API key, the pipeline could automatically create and update agents, reducing all manual steps to zero.

2. **Webhook-driven triggers**: Instead of manual batch runs, n8n webhooks would trigger Pipeline A automatically when a new transcript arrives (e.g., from a Google Drive folder or S3 bucket).

3. **Audio transcription via Whisper**: Add an optional Whisper step (free, local) to handle audio recordings directly, eliminating the transcript-only limitation.

4. **Vector-based extraction**: For highly varied transcripts, augment rule-based extraction with a small embedding model to find relevant context rather than relying on exact regex patterns.

5. **Web dashboard**: A simple FastAPI/Streamlit UI to view all accounts, compare v1 vs v2 diffs, and manually trigger pipeline runs.

6. **CRM integration**: Auto-create customer records in Salesforce/HubSpot when Pipeline A completes.

7. **Conflict escalation workflow**: When v1 and onboarding data conflict, automatically create a review task for a human to resolve before generating v2.

8. **Multi-language support**: Clara currently only handles English. Adding language detection and a handoff protocol for Spanish-speaking callers would be a quick win.

---

## Sample Output Summary

| Account | Company | v1 Questions | v2 Questions Remaining |
|---|---|---|---|
| account_001 | ProFire Solutions | 3 | 0 |
| account_002 | CoolBreeze HVAC | 3 | 0 |
| account_003 | Apex Electrical Services | 3 | 0 |
| account_004 | ShieldGuard Security Systems | 3 | 0 |
| account_005 | TotalFire Protection Inc. | 3 | 0 |

All 5 demo calls → v1 ✅ | All 5 onboarding calls → v2 ✅

---

## Running Tests

```bash
python -m pytest tests/ -v
# Expected: 68 passed
```

Tests cover:
- Time/day parsing helpers
- Business hours extraction
- Emergency definition extraction (clean labels, not raw snippets)
- Integration constraint detection
- Memo extraction (required fields, no hallucination)
- Agent spec generation (prompts, transfer protocol, fallback)
- Memo merge / conflict detection
- Changelog generation
- Deep diff utility
- End-to-end Pipeline A and B
- Idempotency
- Sample output validation