---
name: Bug report
about: Something is broken or behaving incorrectly
title: "[Bug]: "
labels: bug
assignees: ""
---

## Describe the bug

A clear and concise description of what the bug is.

## To reproduce

Steps to reproduce the behavior:

1. Run command `...`
2. With config `...`
3. See error `...`

## Expected behavior

A clear and concise description of what you expected to happen.

## Actual behavior

What actually happened. Include the full error message, exit code, or unexpected output.

## Environment

- **OS**: [e.g., Windows 11, Ubuntu 24.04, macOS 15]
- **Python version**: [output of `python --version`]
- **Commit hash**: [output of `git rev-parse HEAD`]
- **Branch**: [output of `git branch --show-current`]
- **Are you using the scheduler?**: [yes / no / not yet]

## Configuration

- **API keys set**: [Telegram / NewsAPI / Finnhub / none]
- **Telegram channels configured**: [yes / no]
- **Custom `config/*.json` changes**: [yes / no — if yes, describe]

## Logs

Please attach the relevant log file or paste the relevant lines. Do **not** paste your real `.env` file.

```
[paste logs here]
```

Common log locations:
- `logs/pipeline.log` — full pipeline run log
- `logs/pipeline_stdout.log` — pipeline stdout
- `logs/scheduler.log` — scheduler state transitions
- `logs/server.log` — dashboard server errors

## Screenshots

If the bug is visual (dashboard layout, broken rendering), attach a screenshot.

## Additional context

Any other information that might be relevant. Did this work in a previous version? Are there any workarounds you've found?
