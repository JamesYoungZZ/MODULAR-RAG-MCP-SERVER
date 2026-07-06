# Project Codex Instructions

This repository includes project-scoped Codex skills converted from `.claude/skills`.

Use the skills under `.codex/skills` when the user request matches their trigger descriptions:

- `auto-coder`: autonomous spec-driven development from `DEV_SPEC.md`, including syncing spec references, selecting the next task, implementing, testing, and persisting progress.
- `qa-tester`: autonomous QA execution from `QA_TEST_PLAN.md`, including CLI, Dashboard UI, MCP protocol, provider-switch, and data lifecycle tests.
- `resume-writer`: Chinese or English resume project-experience writing based on this Modular RAG MCP Server project.
- `skill-creator`: creating or updating reusable project skills.

When a project skill is used, read its `.codex/skills/<skill-name>/SKILL.md` first, then load only the referenced files needed for the task.

For library, framework, SDK, API, CLI tool, or cloud-service documentation questions, use Context7 MCP first: resolve the library ID, query the docs with the full user question, then answer from the fetched docs.
