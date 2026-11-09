#!/usr/bin/env bash
#
# Pick random gameplay testers from users who can be assigned to repository issues.
#
# Usage:
#   ./scripts/pick-gameplay-testers.sh [--count N] [--repo OWNER/NAME]
#                                      [--exclude LOGIN[,LOGIN...]]...
#
# The script is used by the "Create Gameplay Test Report" workflow and by
# administrators who need to reroll a tester assignment. It prints one login per
# line.
#
# Requirements:
#   - gh, authenticated with `gh auth login`
#   - shuf (GNU coreutils)

set -euo pipefail

COUNT=2
REPO="${REPO:-}"
EXCLUDES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/pick-gameplay-testers.sh [options]

Options:
  --count N            Number of testers to pick. Defaults to 2.
  --exclude LOGINS     Comma-separated logins to exclude. May be repeated.
  --repo OWNER/NAME    Repository whose assignable users are used. Defaults to the
                       repository of the current working directory.
  -h, --help           Show this help.

Environment:
  REPO                 Same as --repo.

The script prints the selected logins one per line. Bots are always excluded.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

while (($# > 0)); do
  case "$1" in
    --count)
      (($# >= 2)) || die "--count requires a value"
      COUNT="$2"
      shift 2
      ;;
    --exclude)
      (($# >= 2)) || die "--exclude requires a value"
      IFS=',' read -r -a logins <<<"$2"
      EXCLUDES+=("${logins[@]}")
      shift 2
      ;;
    --repo)
      (($# >= 2)) || die "--repo requires a value"
      REPO="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$COUNT" =~ ^[0-9]+$ ]] || die "--count must be a positive integer"
((COUNT > 0)) || die "--count must be greater than zero"

command -v gh >/dev/null 2>&1 || die "gh is required but not installed"
command -v shuf >/dev/null 2>&1 || die "shuf is required but not installed"

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
fi

# Lowercase lookup so exclusions are case-insensitive like GitHub logins.
declare -A excluded=()
for login in "${EXCLUDES[@]}"; do
  if [[ -n "$login" ]]; then
    excluded["${login,,}"]=1
  fi
done

# The assignees endpoint reflects the users that can actually be assigned to a
# pull request. The collaborators endpoint can omit inherited/team access and
# therefore produce an empty pool even when assignments are possible.
if ! assignable_output="$(
  gh api --paginate "repos/$REPO/assignees?per_page=100" \
    --jq '.[] | select(.type == "User") | .login'
)"; then
  die "failed to list assignable users for $REPO"
fi

assignable=()
if [[ -n "$assignable_output" ]]; then
  mapfile -t assignable <<<"$assignable_output"
fi

candidates=()
for login in "${assignable[@]}"; do
  if [[ "$login" == *"[bot]" ]]; then
    continue
  fi

  key="${login,,}"
  if [[ -n "${excluded[$key]:-}" ]]; then
    continue
  fi

  candidates+=("$login")
done

if ((${#candidates[@]} < COUNT)); then
  die "need $COUNT candidates but only ${#candidates[@]} are available (assignable users: ${#assignable[@]})"
fi

printf '%s\n' "${candidates[@]}" | shuf -n "$COUNT"
