# Branch Protection for Bloomy News

A guide to protecting the `main` branch — even as a solo maintainer.

## Why branch protection matters for solo maintainers

Branch protection is often associated with team workflows, but it's equally
valuable for solo projects. Without it, a single `git push --force` to `main`
can silently rewrite history, push a broken commit, or delete the branch
entirely. There's no safety net — no second pair of eyes, no CI gate, nothing
to stop a bad push from going live.

Branch protection adds guardrails that force you to slow down *just enough* to
catch mistakes before they land. It turns `main` into a deployment target that
only accepts validated, reviewed changes — exactly the discipline a solo
maintainer needs but is most likely to skip under time pressure.

## Recommended settings for `main`

These settings are tuned for a single-maintainer public repository with CI
already running (Tests + CodeQL).

| Setting | Value | Why |
|---|---|---|
| **Require pull request reviews** | 1 review | Forces you to open a PR and review your own diff. Catches typos, accidental commits, and forces a second look before merging. |
| **Dismiss stale reviews on new pushes** | Enabled | If you push a fix to an open PR, the old approval is invalidated — you must re-review the updated diff. |
| **Require status checks to pass** | `test`, `Analyze (python)` | CI must be green before merging. These are the jobs from `test.yml` and `codeql.yml`. |
| **Require branches to be up to date** | Enabled | Ensures your branch is rebased on the latest `main` before merging, preventing merge conflicts from accumulating. |
| **Require conversation resolution** | Enabled | All review comments must be resolved before merging — no half-addressed feedback. |
| **Include administrators** | Enabled | The protection applies to you too. You cannot bypass it by pushing directly. |
| **Allow force pushes** | Disabled | Prevents `git push --force` from rewriting `main` history. |
| **Allow deletions** | Disabled | Prevents accidental or malicious deletion of the `main` branch. |

## How to set it up via GitHub UI

1. Go to `https://github.com/aaru-sh/bloomy-news/settings/branches`
2. Click **Add branch protection rule**
3. In **Branch name pattern**, enter `main`
4. Enable these options:
   - ☑ **Require a pull request before merging**
     - Under that section, set **Required approvals** to `1`
     - ☑ **Dismiss stale pull request approvals when new commits are pushed**
   - ☑ **Require status checks to pass before merging**
     - Search and add: `test`, `Analyze (python)`
     - ☑ **Require branches to be up to date before merging**
   - ☑ **Require conversation resolution before merging**
   - ☑ **Do not allow bypassing the above settings** (Include administrators)
   - ☑ **Restrict force pushes** — allow force pushes: OFF
   - ☑ **Restrict deletions**
5. Click **Create** / **Save changes**

## How to set it up via `gh api`

One-liner to apply all protections in one call:

```bash
gh api repos/aaru-sh/bloomy-news/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["test", "Analyze (python)"]
  },
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "enforce_admins": true,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true
}
EOF
```

Or use the helper script in this repo:

```bash
bash scripts/setup_branch_protection.sh
```

Run with `--dry-run` to preview without making changes.

## The tradeoff: slightly slower iteration, much safer

Branch protection adds friction. You can no longer do quick `git push` to ship
a typo fix — you have to open a PR, wait for CI, and merge. For a solo
maintainer, this feels like overhead.

But that friction is the point. It means:

- Every change gets a CI check before it touches `main`
- Every change gets a second look (even your own review of the diff)
- History on `main` is always clean and linear
- No accidental force pushes, no deleted branches, no broken `main`
- External contributors (if any) go through the same pipeline

The 2-3 minutes it adds per change is cheap insurance against the one time
you'd push a bug to production at 11pm and not notice until the morning.
