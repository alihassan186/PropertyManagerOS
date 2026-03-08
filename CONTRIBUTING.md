# Contributing to PropertyOS

Thanks for contributing.

## Setup

1. Create a virtual environment and activate it.
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Branch & PR Guidelines

- Use short, focused branches (for example: `fix/autopilot-timeout`)
- Keep pull requests small and easy to review
- Include a clear PR description with:
  - what changed
  - why it changed
  - how you validated it

## Code Quality

Run these before opening a PR:

```bash
ruff check .
black --check .
python -m compileall .
```

## Commit Messages

Use clear imperative messages, e.g.:
- `fix: handle missing apartment_ref in triage`
- `chore: add CI lint and format checks`

## Notes

- Do not commit secrets or `.env`
- Keep changes minimal and scoped to one concern
