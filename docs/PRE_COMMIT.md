# Pre-Commit Hooks

## What Are Pre-Commit Hooks?

Pre-commit hooks are automated checks that run every time you create a git commit. They catch formatting, linting, and hygiene issues *before* they enter the repository, keeping the codebase clean without relying on manual review.

## Installation

```bash
pip install pre-commit
pre-commit install
```

This activates the hooks defined in `.pre-commit-config.yaml`. After installation, the checks run automatically on every `git commit`.

## Hooks Included

| Hook | Purpose |
|------|---------|
| **trailing-whitespace** | Strips trailing whitespace from all files |
| **end-of-file-fixer** | Ensures files end with a newline |
| **check-yaml** | Validates YAML syntax |
| **check-toml** | Validates TOML syntax |
| **check-added-large-files** | Prevents files >500 KB from being committed |
| **check-merge-conflict** | Detects unresolved merge conflict markers |
| **detect-private-key** | Flags accidentally committed private keys |
| **black** | Formats Python code to PEP 8 style (120-char lines) |
| **isort** | Sorts and groups Python imports (black-compatible profile) |
| **flake8** | Lints Python code for style and error violations |

## Running Manually

To run all hooks against every file in the repo:

```bash
pre-commit run --all-files
```

To run a single hook:

```bash
pre-commit run black --all-files
```

## Bypassing Hooks (Emergency Only)

If you need to commit despite a failing hook (e.g., a WIP commit during a hotfix):

```bash
git commit --no-verify -m "WIP: emergency fix"
```

**Use sparingly.** Fix the issues and re-enable hooks as soon as possible.

## Updating Hooks

To update all hooks to their latest versions:

```bash
pre-commit autoupdate
```
