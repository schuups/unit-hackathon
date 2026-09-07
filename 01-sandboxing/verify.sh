#!/usr/bin/env bash
#
# verify.sh -- check that the sandbox actually is one.
#
# Every claim README.md makes about the container is asserted here by running
# the container and looking, rather than by reading the flags back. Exits 0 if
# everything holds, 1 if anything does not, so it is safe to run in front of
# people.
#
# It needs no CSCS API key: where a key is required at all, a deliberately
# invalid one is used, and being rejected by the endpoint is the assertion.
#
#   ./verify.sh                 everything, including the egress tests
#   ./verify.sh --no-network    filesystem and privilege tests only
#   ./verify.sh --build         (re)build both images first
#
set -u

IMAGE="${AGENT_IMAGE:-opencode-cscs:1.18.17}"
PROXY_IMAGE="${AGENT_PROXY_IMAGE:-agent-egress-proxy:1}"
ENGINE="${AGENT_ENGINE:-podman}"
NET="${AGENT_NET:-agent-egress}"
SUBNET="${AGENT_SUBNET:-10.89.7.0/24}"
PROXY_IP="${AGENT_PROXY_IP:-10.89.7.2}"
PROXY_NAME="${AGENT_PROXY_NAME:-agent-proxy}"
OUTER_NET="${AGENT_OUTER_NET:-podman}"
HERE="$(cd "$(dirname "$0")" && pwd)"

DO_NETWORK=1
DO_BUILD=0
for arg in "$@"; do
    case "$arg" in
        --no-network) DO_NETWORK=0 ;;
        --build)      DO_BUILD=1 ;;
        -h|--help)    sed -n '3,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'verify.sh: unknown argument %s\n' "$arg" >&2; exit 2 ;;
    esac
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; N=$'\033[0m'
else
    G=; R=; Y=; B=; N=
fi

FAILED=0
CHECKS=0
section() { printf '\n%s%s%s\n' "$B" "$1" "$N"; }
ok()   { CHECKS=$((CHECKS+1)); printf '  %s✓%s %s\n' "$G" "$N" "$1"; }
bad()  { CHECKS=$((CHECKS+1)); FAILED=$((FAILED+1))
         printf '  %s✗%s %s\n' "$R" "$N" "$1"
         [ $# -gt 1 ] && printf '      %sgot: %s%s\n' "$Y" "$2" "$N"; }
note() { printf '    %s%s%s\n' "$Y" "$1" "$N"; }

# assert <description> <expected> <actual>
assert() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "$3 (expected $2)"; fi; }

# field <key> <blob>  -- pull key=value out of a probe's output
field() { printf '%s\n' "$2" | sed -n "s/^$1=//p" | head -1; }

# -----------------------------------------------------------------------------
section "0. Prerequisites"

command -v "$ENGINE" >/dev/null 2>&1 \
    && ok "$ENGINE on PATH" || { bad "$ENGINE on PATH"; exit 1; }

if ! "$ENGINE" info >/dev/null 2>&1; then
    bad "$ENGINE is responding" "try: podman machine start"
    exit 1
fi
ok "$ENGINE is responding"

if [ "$DO_BUILD" = 1 ]; then
    printf '  building %s ... ' "$IMAGE"
    "$ENGINE" build -q -t "$IMAGE" "$HERE" >/dev/null 2>&1 && echo done || { echo failed; exit 1; }
    printf '  building %s ... ' "$PROXY_IMAGE"
    "$ENGINE" build -q -f "$HERE/Dockerfile.proxy" -t "$PROXY_IMAGE" "$HERE" >/dev/null 2>&1 && echo done || { echo failed; exit 1; }
fi

"$ENGINE" image exists "$IMAGE" \
    && ok "image $IMAGE exists" \
    || { bad "image $IMAGE exists" "run ./verify.sh --build"; exit 1; }

if [ "$DO_NETWORK" = 1 ]; then
    "$ENGINE" image exists "$PROXY_IMAGE" \
        && ok "image $PROXY_IMAGE exists" \
        || { bad "image $PROXY_IMAGE exists" "run ./verify.sh --build"; DO_NETWORK=0; }
fi

# Throwaway stand-ins for ~/agent-sandbox/home and the project directory.
TMPROOT="$(mktemp -d)"
mkdir -p "$TMPROOT/home" "$TMPROOT/workspace"
cleanup() { rm -rf "$TMPROOT"; }
trap cleanup EXIT

SANDBOX_ARGS=(
    --rm -i
    --env CSCS_INFERENCE_API_KEY=not-a-real-key
    --mount "type=bind,src=$TMPROOT/home,dst=/home/agent"
    --mount "type=bind,src=$TMPROOT/workspace,dst=/workspace"
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g,mode=1777
    --read-only
    --cap-drop ALL
    --security-opt no-new-privileges
    --pids-limit 512
    --memory 4g
    --cpus 2
)

# -----------------------------------------------------------------------------
section "1. The container refuses to start without a key"

out="$("$ENGINE" run --rm -i --read-only "$IMAGE" models 2>&1)"; rc=$?
assert "exits non-zero when CSCS_INFERENCE_API_KEY is unset" "1" "$rc"
case "$out" in
    *"CSCS_INFERENCE_API_KEY is not set"*) ok "says why, in one line you can act on" ;;
    *) bad "says why, in one line you can act on" "$(printf '%s' "$out" | head -1)" ;;
esac

# -----------------------------------------------------------------------------
section "2. Identity, privilege and the filesystem"

# One container, one pass, everything measured from the inside.
PROBE='
echo uid=$(id -u)
echo user=$(id -un)
echo nnp=$(grep ^NoNewPrivs /proc/self/status | tr -d "\t " | cut -d: -f2)
echo capeff=$(grep ^CapEff /proc/self/status | tr -d "\t " | cut -d: -f2)
for p in / /etc /usr /opt; do
    n=$(echo "$p" | tr -d /); [ -z "$n" ] && n=root
    if touch "$p/.verify-probe" 2>/dev/null; then echo "write_$n=ALLOWED"; rm -f "$p/.verify-probe"
    else echo "write_$n=denied"; fi
done
for p in /home/agent /workspace /tmp; do
    n=$(basename "$p")
    if touch "$p/.verify-probe" 2>/dev/null; then echo "write_$n=ok"; rm -f "$p/.verify-probe"
    else echo "write_$n=DENIED"; fi
done
echo tmp_fstype=$(awk "\$2 == \"/tmp\" {print \$3}" /proc/mounts | head -1)
echo tmp_size=$(awk "\$2 == \"/tmp\" {print \$4}" /proc/mounts | tr "," "\n" | grep "^size=" | head -1)
printf "#!/bin/sh\necho ran\n" > /tmp/probe.sh && chmod +x /tmp/probe.sh
if [ "$(/tmp/probe.sh 2>/dev/null)" = "ran" ]; then echo tmp_exec=ok; else echo tmp_exec=DENIED; fi
command -v ssh >/dev/null 2>&1 && echo ssh=present || echo ssh=absent
command -v python3 >/dev/null 2>&1 && echo py3=present || echo py3=absent
python3 -c "import requests, yaml, pytest" 2>/dev/null && echo pylibs=ok || echo pylibs=MISSING
[ -e /Users ] || [ -e /host ] && echo host_home=VISIBLE || echo host_home=absent
echo mounts=$(awk "{print \$2}" /proc/mounts | grep -c .)
'
p="$("$ENGINE" run "${SANDBOX_ARGS[@]}" --entrypoint sh "$IMAGE" -c "$PROBE" 2>&1)"

assert "runs as uid 1000, not root"            "1000"             "$(field uid "$p")"
assert "the user is 'agent'"                   "agent"            "$(field user "$p")"
assert "NoNewPrivs is set"                     "1"                "$(field nnp "$p")"
assert "CapEff is all zeros (no capabilities)" "0000000000000000" "$(field capeff "$p")"

section "   ...root filesystem is read-only"
for d in root etc usr opt; do
    assert "/$([ "$d" = root ] && echo '' || echo "$d") is not writable" "denied" "$(field "write_$d" "$p")"
done

section "   ...and exactly three paths are writable"
assert "/home/agent is writable" "ok" "$(field write_agent "$p")"
assert "/workspace is writable"  "ok" "$(field write_workspace "$p")"
assert "/tmp is writable"        "ok" "$(field write_tmp "$p")"
assert "/tmp is a tmpfs (in RAM, gone on exit)" "tmpfs" "$(field tmp_fstype "$p")"
assert "a script written to /tmp can be executed" "ok" "$(field tmp_exec "$p")"
assert "ssh client present (section 3: it has no route out)" "present" "$(field ssh "$p")"
assert "python3 present"                                     "present" "$(field py3 "$p")"
assert "requests, yaml and pytest importable"                "ok"      "$(field pylibs "$p")"
assert "the host's home is not visible" "absent" "$(field host_home "$p")"

# The tmpfs options, measured rather than assumed. Docker documents
# rw,noexec,nosuid,size=65536k as its --tmpfs defaults; this engine may differ,
# so print what it actually did and then prove noexec is a real option.
tmpfs_probe='awk "\$2==\"/tmp\"{print \$4}" /proc/mounts; printf "#!/bin/sh\necho ran\n" > /tmp/p.sh; chmod +x /tmp/p.sh; /tmp/p.sh >/dev/null 2>&1 && echo EXEC=allowed || echo EXEC=blocked'

defaults="$("$ENGINE" run --rm -i --read-only --tmpfs /tmp \
    --env CSCS_INFERENCE_API_KEY=x --entrypoint sh "$IMAGE" -c "$tmpfs_probe" 2>&1)"
note "bare '--tmpfs /tmp' on this engine: $(printf '%s' "$defaults" | head -1 | sed 's/context="[^"]*",\{0,1\}//' | tr ',' ' ' | tr -s ' ')"
note "               and exec there is: $(printf '%s\n' "$defaults" | sed -n 's/^EXEC=//p')"

explicit="$("$ENGINE" run --rm -i --read-only --tmpfs /tmp:noexec \
    --env CSCS_INFERENCE_API_KEY=x --entrypoint sh "$IMAGE" -c "$tmpfs_probe" 2>&1)"
assert "asking for noexec really does block execution from /tmp" \
    "blocked" "$(printf '%s\n' "$explicit" | sed -n 's/^EXEC=//p')"

sized="$(field tmp_size "$p")"
assert "the 1 GiB cap on /tmp is applied" "size=1048576k" "$sized"

# -----------------------------------------------------------------------------
if [ "$DO_NETWORK" = 0 ]; then
    section "3. Network egress -- SKIPPED (--no-network)"
else
section "3. Network egress"

if ! "$ENGINE" network exists "$NET" 2>/dev/null; then
    "$ENGINE" network create --internal --disable-dns --subnet "$SUBNET" "$NET" >/dev/null 2>&1
fi
"$ENGINE" network exists "$NET" && ok "internal network $NET exists" || bad "internal network $NET exists"

internal="$("$ENGINE" network inspect "$NET" --format '{{.Internal}}' 2>/dev/null)"
assert "the network is internal (no gateway, so no route out)" "true" "$internal"

if [ "$("$ENGINE" inspect -f '{{.State.Running}}' "$PROXY_NAME" 2>/dev/null)" != "true" ]; then
    "$ENGINE" rm -f "$PROXY_NAME" >/dev/null 2>&1
    "$ENGINE" run -d --name "$PROXY_NAME" \
        --network "${NET}:ip=${PROXY_IP}" --network "$OUTER_NET" \
        --read-only --cap-drop ALL --security-opt no-new-privileges \
        --pids-limit 64 --memory 128m "$PROXY_IMAGE" >/dev/null 2>&1
    sleep 2
fi
[ "$("$ENGINE" inspect -f '{{.State.Running}}' "$PROXY_NAME" 2>/dev/null)" = "true" ] \
    && ok "egress proxy $PROXY_NAME is running" || bad "egress proxy $PROXY_NAME is running"

NETARGS=(
    --network "$NET" --dns none
    --env "HTTPS_PROXY=http://${PROXY_IP}:8888"
    --env "HTTP_PROXY=http://${PROXY_IP}:8888"
    --env "https_proxy=http://${PROXY_IP}:8888"
    --env "http_proxy=http://${PROXY_IP}:8888"
)

NETPROBE='
ip route | grep -q "^default" && echo default_route=PRESENT || echo default_route=absent
[ -s /etc/resolv.conf ] && echo resolver=PRESENT || echo resolver=absent
curl -sS -m 8 --noproxy "*" -o /dev/null https://1.1.1.1/ 2>/dev/null \
    && echo direct=REACHED || echo direct=blocked
echo allow_cscs=$(curl -sS -m 25 -o /dev/null -w "%{http_code}" https://api.inference.cscs.ch/v1/models 2>/dev/null)
echo allow_catalogue=$(curl -sS -m 25 -o /dev/null -w "%{http_code}" https://models.opencode.ai/api.json 2>/dev/null)
echo deny_other=$(curl -sS -m 15 -o /dev/null -w "%{http_code}" https://example.com/ 2>&1 | grep -o "403" | head -1)
echo deny_npm=$(curl -sS -m 15 -o /dev/null -w "%{http_code}" https://registry.npmjs.org/ 2>&1 | grep -o "403" | head -1)
echo deny_port=$(curl -sS -m 15 -o /dev/null -w "%{http_code}" https://api.inference.cscs.ch:22/ 2>&1 | grep -o "403" | head -1)
'
n="$("$ENGINE" run "${SANDBOX_ARGS[@]}" "${NETARGS[@]}" --entrypoint sh "$IMAGE" -c "$NETPROBE" 2>&1)"

assert "the container has no default route"          "absent"  "$(field default_route "$n")"
assert "the container has no DNS resolver of its own" "absent" "$(field resolver "$n")"
assert "a direct connection to the internet fails"   "blocked" "$(field direct "$n")"
assert "api.inference.cscs.ch is reachable via the proxy (401 = rejected key, not blocked)" \
                                                     "401"     "$(field allow_cscs "$n")"
assert "the model catalogue is reachable via the proxy" "200"   "$(field allow_catalogue "$n")"
assert "an unlisted host is refused by the proxy"    "403"     "$(field deny_other "$n")"
assert "registry.npmjs.org is refused by the proxy"  "403"     "$(field deny_npm "$n")"
assert "CONNECT to a port other than 443 is refused" "403"     "$(field deny_port "$n")"
fi

# -----------------------------------------------------------------------------
section "4. opencode itself"

MODELS_ARGS=("${SANDBOX_ARGS[@]}")
[ "$DO_NETWORK" = 1 ] && MODELS_ARGS+=("${NETARGS[@]}")

models="$("$ENGINE" run "${MODELS_ARGS[@]}" "$IMAGE" models 2>&1)"
count="$(printf '%s\n' "$models" | grep -c '^cscs/')"
assert "all 10 CSCS models resolve" "10" "$count"
printf '%s\n' "$models" | grep -q '^cscs/moonshotai/Kimi-K2.7-Code$' \
    && ok "the default model is in the list" \
    || bad "the default model is in the list"

if [ "$DO_NETWORK" = 1 ]; then
    # The provider SDK question: the config declares "npm": "@ai-sdk/anthropic",
    # and npm is blocked at the proxy. If opencode still reaches the endpoint --
    # and is turned away for the key, not the network -- the SDK is built in and
    # nothing needs pre-warming.
    run_out="$("$ENGINE" run "${SANDBOX_ARGS[@]}" "${NETARGS[@]}" "$IMAGE" run "hi" 2>&1)"
    case "$run_out" in
        *"invalid API key"*|*"Forbidden"*|*401*)
            ok "reaches the endpoint with npm blocked (the SDK is built in)" ;;
        *)
            bad "reaches the endpoint with npm blocked" "$(printf '%s' "$run_out" | tr -d '\r' | tail -2 | tr '\n' ' ')" ;;
    esac
fi

# -----------------------------------------------------------------------------
if [ "$DO_NETWORK" = 1 ]; then
    printf '\n  the egress proxy is left running for `oc`; `oc-proxy-down` removes it\n'
fi

printf '\n%s' "$B"
if [ "$FAILED" -eq 0 ]; then
    printf '%s%d checks, all passed.%s\n' "$G" "$CHECKS" "$N"
    exit 0
else
    printf '%s%d of %d checks FAILED.%s\n' "$R" "$FAILED" "$CHECKS" "$N"
    exit 1
fi
