#!/usr/bin/env bash
# Offline regression tests. No connection to a Docker daemon or live host is made.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# The default SmartDNS service must be identical to the preserved legacy block.
# This prevents config drift in image pin, mounts, network, restart and healthcheck.
diff -u \
  <(sed -n '/^  smartdns:$/,$p' "$ROOT/macmini/network.yaml") \
  <(sed -n '/^  smartdns:$/,$p' "$ROOT/macmini/smartdns.yaml")
[[ $(grep -c '^  [a-zA-Z0-9_-]*:$' "$ROOT/macmini/smartdns.yaml") -eq 1 ]]
grep -q '^name: homelab_network$' "$ROOT/macmini/smartdns.yaml"

# Run the real current.sh in a fake checkout with fake docker/python3 executables.
mkdir -p "$TMP/repo/scripts" "$TMP/bin"
cp "$ROOT/scripts/current.sh" "$TMP/repo/scripts/current.sh"
printf 'test-only\n' > "$TMP/repo/.env"
cat > "$TMP/bin/python3" <<'MOCKPY'
#!/usr/bin/env bash
cat > /dev/null
MOCKPY
cat > "$TMP/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == context ]]; then
  printf 'unix:///var/run/docker.sock\n'
  exit 0
fi
if [[ "$1" == compose && ( "$2" == config || "$2" == up ) && "$3" == --help ]]; then
  [[ "$2" == config ]] && echo '--format' || echo '--wait-timeout'
  exit 0
fi
if [[ "$1" == compose ]]; then
  [[ "${COMPOSE_REMOVE_ORPHANS:-}" == false ]] || { echo 'Unsafe orphan setting' >&2; exit 1; }
  shift
  file=''
  while (($#)); do
    if [[ "$1" == -f ]]; then file=$2; shift 2; break; fi
    shift
  done
  op=$1
  printf '%s %s\n' "${file##*/}" "$op" >> "$TEST_LOG"
  if [[ "$op" == config ]]; then printf '{"services":{}}\n'; fi
  exit 0
fi
exit 1
MOCK
chmod +x "$TMP/bin/docker" "$TMP/bin/python3"
export TEST_LOG="$TMP/calls" PATH="$TMP/bin:$PATH"
script="$TMP/repo/scripts/current.sh"

plan() {
  bash "$script" plan macmini "$@" | sed -n '3,$p' | sed 's/^  //'
}
assert_plan() {
  local expected=$1; shift
  local actual
  actual=$(plan "$@")
  [[ "$actual" == "$expected" ]] || {
    printf 'Unexpected plan\nEXPECTED:\n%s\nACTUAL:\n%s\n' "$expected" "$actual" >&2
    exit 1
  }
}
expect_invalid() {
  if bash "$script" "$@" >/dev/null 2>&1; then
    printf 'Unexpectedly accepted: %s\n' "$*" >&2
    exit 1
  fi
}
DEFAULT=$'macmini/smartdns.yaml\nmacmini/collect-metadata.yaml\nmacmini/immich-ml.yaml'
ADGUARD=$'macmini/network.yaml\nmacmini/collect-metadata.yaml\nmacmini/immich-ml.yaml'
NPM=$'macmini/smartdns.yaml\nmacmini/collect-metadata.yaml\nmacmini/npm.yaml\nmacmini/immich-ml.yaml'
BOTH=$'macmini/network.yaml\nmacmini/collect-metadata.yaml\nmacmini/npm.yaml\nmacmini/immich-ml.yaml'
assert_plan "$DEFAULT"
assert_plan "$ADGUARD" --legacy-adguard
assert_plan "$NPM" --legacy-npm
assert_plan "$BOTH" --legacy-adguard --legacy-npm
assert_plan "$BOTH" --legacy-npm --legacy-adguard
expect_invalid plan nas --legacy-npm
expect_invalid plan nas --legacy-adguard
expect_invalid plan macmini --unknown
expect_invalid plan macmini --legacy-npm --legacy-npm
expect_invalid plan macmini --legacy-adguard --legacy-adguard
expect_invalid plan macmini --legacy-npm --legacy-adguard --legacy-npm
expect_invalid plan unknown

run_and_assert() {
  local action=$1 expected=$2; shift 2
  : > "$TEST_LOG"
  bash "$script" "$action" macmini "$@" >/dev/null
  local actual
  actual=$(cat "$TEST_LOG")
  [[ "$actual" == "$expected" ]] || {
    printf 'Unexpected %s calls for %s\nEXPECTED:\n%s\nACTUAL:\n%s\n' \
      "$action" "$*" "$expected" "$actual" >&2
    exit 1
  }
}
# check has config reads, never pulls or starts services.
run_and_assert check $'smartdns.yaml config\ncollect-metadata.yaml config\nimmich-ml.yaml config'
# apply pull/up/ps stages must target exactly the selected services.
default_calls=$'smartdns.yaml config\ncollect-metadata.yaml config\nimmich-ml.yaml config\nsmartdns.yaml pull\ncollect-metadata.yaml pull\nimmich-ml.yaml pull\nsmartdns.yaml up\ncollect-metadata.yaml up\nimmich-ml.yaml up\nsmartdns.yaml ps\ncollect-metadata.yaml ps\nimmich-ml.yaml ps'
legacy_calls=$'network.yaml config\ncollect-metadata.yaml config\nnpm.yaml config\nimmich-ml.yaml config\nnetwork.yaml pull\ncollect-metadata.yaml pull\nnpm.yaml pull\nimmich-ml.yaml pull\nnetwork.yaml up\ncollect-metadata.yaml up\nnpm.yaml up\nimmich-ml.yaml up\nnetwork.yaml ps\ncollect-metadata.yaml ps\nnpm.yaml ps\nimmich-ml.yaml ps'
run_and_assert apply "$default_calls"
run_and_assert apply "$legacy_calls" --legacy-adguard --legacy-npm
printf 'PASS: SmartDNS parity; exact plans; invalid inputs; mocked check/default/legacy apply\n'
