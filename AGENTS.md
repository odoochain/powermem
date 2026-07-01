# AGENTS.md — PowerMem

## Project overview

PowerMem is a Python library providing persistent, self-evolving memory for AI agents. It ships as a pip-installable package with optional CLI (`pmem`), HTTP server (`powermem-server`), and MCP server (`powermem-mcp`).

## Quick commands

```bash
# Install with all dev dependencies (uses uv, not pip)
make install-dev

# Run tests (excludes e2e by default)
make test

# Run specific test suites
make test-unit
make test-integration
make test-e2e

# Run a single test file
make test-specific FILE=tests/unit/test_memory.py

# Lint (high-signal only: F601, F821, E999)
make lint

# Full lint
make lint-full

# Format code (black + isort, line length 88)
make format

# Check formatting without modifying
make format-check

# Type check (mypy, strict settings)
make type-check
```

## Architecture

### Source layout

- `src/powermem/` — Main library (SDK, MCP, CLI, integrations)
- `src/server/` — FastAPI HTTP API server + dashboard serving
- `dashboard/` — Frontend (Vite + React), built separately then injected into `src/server/dashboard/`
- `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/regression/` — Test suites
- `apps/claude-code-plugin/` — Claude Code integration plugin
- `packages/powermem-mcp/` — Standalone `powermem-mcp` wrapper package
- `scripts/` — Build, version, and utility scripts
- `benchmark/` — Benchmark suites (LOCOMO, AppWorld)

### Key entrypoints

- `src/powermem/__init__.py` — Public SDK API (`Memory`, `auto_config`)
- `src/powermem/cli/main:cli` — CLI (`pmem`, `powermem-cli`)
- `src/powermem/mcp/cli:main` — MCP server entrypoint (`powermem-mcp`)
- `src/server/cli/server:server` — HTTP API server entrypoint (`powermem-server`)
- `src/server/main.py` — FastAPI app definition

### Dashboard build flow

The dashboard frontend (in `dashboard/`) must be built and injected before the server can serve it:

```bash
make build-dashboard  # Builds with pnpm/npm, copies dist/ to src/server/dashboard/
make server-start     # Now serves dashboard at /dashboard/
```

In CI, the dashboard is built as a separate job and the artifact is downloaded/injected before the main build.

## Version management

Version is defined in multiple files. Use `make bump-version VERSION=x.y.z` to update them all:

- `pyproject.toml` (project version)
- `src/powermem/version.py` (`__version__`)
- `src/powermem/core/telemetry.py` (telemetry version field)
- `src/powermem/core/audit.py` (audit version field)
- `packages/powermem-mcp/pyproject.toml` (wrapper version + dependency pin)

Run `make check-package-versions` to verify alignment.

## Testing

- **Markers**: `unit`, `integration`, `e2e`, `e2e_config`, `api`, `slow`
- **CI runs**: `pytest --ignore=tests/regression -m "not e2e and not e2e_config"` on Python 3.11 and 3.12
- **e2e_config tests**: Require real configuration files (not run in default suite)
- **Regression tests**: Run separately in Docker (`make test-claude-hook-docker`)
- **Test path**: `pythonpath = ["src"]` in pytest config, so imports use `powermem.xxx` directly

## Code quality

- **Formatter**: black (line-length 88, target Python 3.11) + isort (profile "black")
- **Linter**: flake8 (high-signal: F601, F821, E999)
- **Type checker**: mypy with strict settings (`disallow_untyped_defs`, `warn_unreachable`, etc.)
- **CI lint order**: lint → format-check → test (CI runs `make ci-full` for full checks)

## Environment

- Copy `.env.example` to `.env` and set your LLM API key (the only required credential)
- `.env.example.full` documents every available knob
- `pmem config init` walks through setup interactively
- Default storage: SQLite (or OceanBase/SeekDB on Linux)
- Default embedder: local `all-MiniLM-L6-v2` (auto-downloads, no API key needed)

## Gotchas

- Dashboard must be built (`make build-dashboard`) before server can serve it at `/dashboard/`
- Version bump requires updating 5 files; use `make bump-version VERSION=x.y.z`
- `powermem-mcp` wrapper package version must stay aligned with main `powermem` version
- Tests use `src/` as pythonpath — imports are `powermem.xxx`, not relative
- CI excludes regression tests and e2e by default; regression tests run in Docker
- `uv` is the package manager (not pip); Makefile uses `UV_RUN`, `UV_DEV`, `UV_TEST` patterns
- pgvector now supports hybrid search (vector + FTS with RRF/weighted fusion) — configure via `hybrid_search=True` in PGVectorConfig
