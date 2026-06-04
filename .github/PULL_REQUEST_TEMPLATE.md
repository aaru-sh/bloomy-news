---
name: Pull request
about: Submit code changes for review
title: "[PR]: "
labels: ""
assignees: ""
---

## Summary

One or two sentences. What does this PR change, and why?

## Related issues

Closes #N — or `Refs #N` if it doesn't fully close the issue.

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Refactor (no functional change)
- [ ] Test addition or improvement
- [ ] Build / CI / tooling

## How was this tested?

Describe the tests you ran to verify your change. Include:

- Which test files / test cases you added or modified
- Manual testing you did (commands run, expected vs actual output)
- Any edge cases you considered

```bash
# commands you ran
python -m unittest tests.test_fixes -v
# output
..................
Ran 18 tests in 0.043s
OK
```

## Screenshots (if applicable)

If the PR changes the UI, attach before/after screenshots.

## Checklist

- [ ] My code follows the project's code style (see [CONTRIBUTING.md](../../blob/main/CONTRIBUTING.md#code-style))
- [ ] I have added tests that prove my fix / feature works
- [ ] New and existing unit tests pass locally
- [ ] I have updated the [CHANGELOG.md](../../blob/main/CHANGELOG.md) under the `[Unreleased]` section
- [ ] I have updated the relevant documentation in `README.md` or `docs/`
- [ ] I have not introduced any new dependencies (or explained why one is needed in the PR description)
- [ ] I have not introduced any new top-level env vars (or updated `.env.example` accordingly)
- [ ] I have not committed any secrets, real API keys, or sensitive configuration

## Additional context

Anything else the reviewer should know. Mention any open questions, areas of uncertainty, or specific aspects you'd like feedback on.
