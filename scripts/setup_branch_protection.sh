#!/usr/bin/env bash
#
# setup_branch_protection.sh
# Configures branch protection rules on the main branch of aaru-sh/bloomy-news.
#
# Usage:
#   bash scripts/setup_branch_protection.sh            # apply protection
#   bash scripts/setup_branch_protection.sh --dry-run  # preview only
#
# Requires: gh CLI authenticated with admin access to the repo.

set -euo pipefail

REPO="aaru-sh/bloomy-news"
BRANCH="main"

# --- Colors ---------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Flags ----------------------------------------------------------------

DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --help|-h)
      echo "Usage: $0 [--dry-run]"
      echo ""
      echo "  --dry-run   Show what would be done without making changes."
      exit 0
      ;;
  esac
done

# --- Preflight checks -----------------------------------------------------

echo -e "${CYAN}Preflight checks${NC}"

# Check gh CLI
if ! command -v gh &>/dev/null; then
  echo -e "${RED}Error: gh CLI not found.${NC} Install it from https://cli.github.com/"
  exit 1
fi
echo -e "  ${GREEN}[ok]${NC} gh CLI found: $(gh --version | head -1)"

# Check auth
if ! gh auth status &>/dev/null 2>&1; then
  echo -e "${RED}Error: gh not authenticated. Run 'gh auth login' first.${NC}"
  exit 1
fi
echo -e "  ${GREEN}[ok]${NC} gh is authenticated"

# Check repo access
if ! gh repo view "$REPO" &>/dev/null 2>&1; then
  echo -e "${RED}Error: Cannot access $REPO. Check permissions.${NC}"
  exit 1
fi
echo -e "  ${GREEN}[ok]${NC} Repository $REPO is accessible"

# --- Build payload --------------------------------------------------------

PAYLOAD=$(cat <<'ENDJSON'
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
ENDJSON
)

# --- Summary --------------------------------------------------------------

echo ""
echo -e "${CYAN}Branch protection configuration for ${REPO}@${BRANCH}${NC}"
echo -e "  Status checks:       ${GREEN}test${NC}, ${GREEN}Analyze (python)${NC} (strict: up-to-date required)"
echo -e "  PR reviews:          ${GREEN}1 approval${NC}, stale reviews dismissed"
echo -e "  Conversation:        ${GREEN}resolution required${NC}"
echo -e "  Administrators:      ${GREEN}included${NC} (cannot bypass)"
echo -e "  Force pushes:        ${RED}disabled${NC}"
echo -e "  Branch deletion:     ${RED}disabled${NC}"
echo ""

# --- Execute or preview ---------------------------------------------------

if [ "$DRY_RUN" = true ]; then
  echo -e "${YELLOW}DRY RUN — no changes will be made.${NC}"
  echo ""
  echo "The following PUT request would be sent:"
  echo ""
  echo "  PUT repos/$REPO/branches/$BRANCH/protection"
  echo ""
  echo "$PAYLOAD" | python3 -m json.tool 2>/dev/null || echo "$PAYLOAD"
  echo ""
  echo -e "${YELLOW}To apply, run without --dry-run:${NC}"
  echo "  bash scripts/setup_branch_protection.sh"
  exit 0
fi

# --- Confirm --------------------------------------------------------------

echo -e "${YELLOW}This will apply branch protection to $REPO/$BRANCH.${NC}"
read -r -p "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

# --- Apply ----------------------------------------------------------------

echo ""
echo -e "${CYAN}Applying branch protection...${NC}"

if echo "$PAYLOAD" | gh api "repos/$REPO/branches/$BRANCH/protection" --method PUT --input - 2>&1; then
  echo ""
  echo -e "${GREEN}Branch protection enabled successfully.${NC}"
  echo ""
  echo "Verify at: https://github.com/$REPO/settings/branches"
else
  echo ""
  echo -e "${RED}Error: Failed to apply branch protection.${NC}"
  echo "Check that:"
  echo "  1. You are an admin of $REPO"
  echo "  2. The branch '$BRANCH' exists"
  echo "  3. GitHub API rate limits are not exceeded"
  exit 1
fi
