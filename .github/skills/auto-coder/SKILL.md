---
name: auto-coder
description: Autonomous spec-driven development agent. Syncs DEV_SPEC.md into chapter-based reference files, identifies the next pending task from the schedule, implements code following spec architecture and patterns, runs tests with up to 3 auto-fix rounds, and persists progress with atomic commits. Use when user says "auto code", "自动开发", "自动写代码", "auto dev", "一键开发", "autopilot", or wants fully automated spec-to-code workflow.
---

# Auto Coder

One trigger completes **read spec → find task → code → test → persist progress**.

Optional modifiers: append a task ID (e.g. `auto code B2`) to target a specific task, or `--no-commit` to skip git commit.

---

## Pipeline

```
Sync Spec → Find Task → Implement → Test (≤3 fix rounds) → Persist
```

Pause only at the end for commit confirmation. Run everything else autonomously.

> **⚠️ CRITICAL: Activate `.venv` before ANY `python`/`pytest` command (idempotent, re-run if unsure).**
> - **Windows**: `.\.venv\Scripts\Activate.ps1`
> - **macOS/Linux**: `source .venv/bin/activate`

## Reference Map

All files under `.github/skills/auto-coder/references/`:

| File | Content | When to Read |
|------|---------|-------------|
| `01-overview.md` | Project overview & goals | First task or when needing project context |
| `02-features.md` | Feature specifications | When implementing feature-related tasks |
| `03-tech-stack.md` | Tech stack & dependencies | When choosing libraries or patterns |
| `04-testing.md` | Testing conventions | When writing tests |
| `05-architecture.md` | Architecture & module design | When creating/modifying modules |
| `06-schedule.md` | Task schedule & status | Every cycle (Sync Spec step) |
| `07-future.md` | Future roadmap | When planning or assessing scope |

---

### 1. Sync Spec

```powershell
python .github/skills/auto-coder/scripts/sync_spec.py
```

Then read the schedule file to get task statuses:
- Read `.github/skills/auto-coder/references/06-schedule.md`

Task markers:

| Marker | Status |
|--------|--------|
| `[ ]` / `⬜` | Not started |
| `[~]` / `🔶` / `(进行中)` | In progress |
| `[x]` / `✅` / `(已完成)` | Completed |

---

### 2. Find Task

Pick the first `IN_PROGRESS` task, then the first `NOT_STARTED`. If user specified a task ID, use that directly.

Quick-check predecessor artifacts exist (file-level only). On mismatch, log a warning and continue — only stop if the target task itself is blocked.

---

### 3. Implement

1. **Read relevant spec** from `.github/skills/auto-coder/references/`:
   - Architecture: `05-architecture.md`
   - Tech details: `03-tech-stack.md`
   - Testing conventions: `04-testing.md`

2. **Extract** from spec: inputs/outputs, design principles (Pluggable? Config-driven? Factory?), file list, acceptance criteria.

3. **Plan** files to create/modify before writing any code.

4. **Code** — project-specific rules:
   - Treat spec as single source of truth
   - Use `config/settings.yaml` values, never hardcode
   - Match existing codebase patterns and style

5. **Write tests** alongside code:
   - Place in `tests/unit/` or `tests/integration/` per spec
   - Mock external deps in unit tests

6. **Self-review** before running tests: verify all planned files exist and tests import correctly.

---

### 4. Test & Auto-Fix

```

Round 0..2:
  Run pytest on relevant test file
  If pass → go to step 5
  If fail → analyze error, apply fix, re-run

Round 3 still failing → STOP, show failure report to user
```

---

### 5. Persist

1. **Update `DEV_SPEC.md`** (global file): change task marker `[ ]` → `[x]`
2. **Re-sync**: `python .github/skills/auto-coder/scripts/sync_spec.py --force`
3. **Write interview story on section completion**:
    - When a completed task also completes a schedule section/phase (for example all tasks in Phase B are `[x]`), create or update a separate Markdown file under `docs/interview-stories/`.
    - File naming convention: `phase-<letter-or-name>-<short-topic>.md` (for example `phase-b-pluggable-libs-layer.md`).
    - Include two concise sections:
       - `Shorter 45-Second Version`: a spoken interview narrative that summarizes what was built, key decisions, and impact.
       - `One Strong Interview Framing`: a strong answer to a likely interviewer follow-up such as the hardest part, tradeoff, or design decision.
    - Keep it interview-ready: clear, concrete, and focused on engineering decisions rather than task-by-task changelog detail.
4. **Show summary & ask**:

Before asking for the commit choice, include four sections:
- **Technical summary**: describe the implementation in engineering terms, including the main abstractions, modules, contracts, tests, and validation results.
- **Plain-language study summary**: write a beginner-friendly explanation in 2-4 short paragraphs. Explain what was coded, why each touched file matters, how the new code fits into the project flow, and any important vocabulary a beginner should learn. Avoid assuming the user already knows architecture terms; briefly unpack terms such as contract, factory, metadata, pipeline, vector, or serialization when they appear.
- **Benefit**: explain what practical value the change adds now and what it enables for future tasks.
- **Study pointers**: list 3-5 concrete files, functions, or concepts the user can review next to understand the change more deeply.

```
✅ [A3] 配置加载与校验 — done
   Files: src/core/settings.py, tests/unit/test_settings.py
   Tests: 8/8 passed
   Technical summary: Added typed settings models, YAML loading, validation, and unit coverage.
   Plain-language study summary: This change teaches the app how to read one central configuration file before it starts doing real work. The settings file is like the project's control panel: it says which LLM provider, embedding provider, vector store, retrieval strategy, and logging setup should be used. The code turns that YAML text into typed Python objects, then checks that required fields are present so the program fails early with a useful message instead of breaking later in a confusing place.
   Study pointers: src/core/settings.py, config/settings.yaml, tests/unit/test_config_loading.py, dataclasses, validation.
   Benefit: Future features can rely on one validated config source instead of scattered hardcoded values.
   Commit: feat(config): [A3] implement config loader

   "commit" → git add + commit
   "skip"   → end
   "next"   → commit + start next task
```

On "next", loop back to step 1 and start the next task.
