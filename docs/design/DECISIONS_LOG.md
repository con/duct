# Decision log — collector / measurement POC

Records every non-trivial design or implementation decision, each with a
one-line rationale. **Bold** marks decisions I was unsure about and that are
worth revisiting.

See `POC_BRIEF.md` for the goal and `resource-collectors.md` for the design.

## Environment / setup

- Container venv lives at `.venv` (created with `uv`, not the host's
  `~/.venvs/duct`); installed `-e .[all]` plus `tox`, `pytest`, and `psutil`
  so both the stdlib-only and optional-psutil paths can be exercised. Rationale:
  the container ships `uv` only (no pip/tox/venv preinstalled).
- Tests live under `test/` (singular), matching the existing repo layout — the
  brief/CLAUDE.md say `tests/`, but I follow the repo's actual convention.
  Rationale: behavior-preserving, don't fork the test tree.

## Decisions

<!-- newest first; one line each, **bold** the uncertain ones -->
