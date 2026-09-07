# --- sandboxed opencode ------------------------------------------------------
#
# Copy this file to ~/agent-sandbox/oc.sh and source it from ~/.zshrc:
#
#     [ -f "$HOME/agent-sandbox/oc.sh" ] && source "$HOME/agent-sandbox/oc.sh"
#
# It gives you `oc` (run the agent), plus `oc-proxy-log`, `oc-proxy-down` and
# `oc-doctor`. See README.md in 01-sandboxing/.
#
# Written for Podman. Docker works for everything except the egress network --
# see "Restricting network egress" in README.md for what differs.

export AGENT_ROOT="$HOME/agent-sandbox"
export AGENT_KEYFILE="$AGENT_ROOT/secrets/cscs-api-key"
export AGENT_IMAGE="opencode-cscs:1.18.17"
export AGENT_ENGINE="podman"

# Egress mode:
#   proxy  (default) internal network, no route out, allowlist proxy sidecar
#   open             the engine's normal bridge -- the agent can reach anything
#   none             no network at all; nothing works, which is the point
export AGENT_EGRESS="${AGENT_EGRESS:-proxy}"

export AGENT_PROXY_IMAGE="agent-egress-proxy:1"
export AGENT_PROXY_NAME="agent-proxy"
export AGENT_NET="agent-egress"
export AGENT_SUBNET="10.89.7.0/24"
export AGENT_PROXY_IP="10.89.7.2"
export AGENT_OUTER_NET="podman"        # docker: bridge

# Extra engine flags, space-separated, e.g. --userns=keep-id on rootless
# Podman under Linux.
export AGENT_RUN_ARGS="${AGENT_RUN_ARGS:-}"

# -----------------------------------------------------------------------------
# The egress side: an internal network with no gateway, and one container on it
# that is also attached to a normal network. That container is the only route
# out, and it only forwards to hosts on its allowlist.
# -----------------------------------------------------------------------------
oc-proxy-up() {
    if ! "$AGENT_ENGINE" network exists "$AGENT_NET" 2>/dev/null; then
        # --internal: no gateway, so the kernel has no route off this bridge.
        # --disable-dns: no resolver either. The agent resolves nothing itself;
        # the proxy does the resolving, which is what makes the allowlist bite.
        "$AGENT_ENGINE" network create --internal --disable-dns \
            --subnet "$AGENT_SUBNET" "$AGENT_NET" >/dev/null || return 1
    fi

    if [ "$("$AGENT_ENGINE" inspect -f '{{.State.Running}}' "$AGENT_PROXY_NAME" 2>/dev/null)" = "true" ]; then
        return 0
    fi
    "$AGENT_ENGINE" rm -f "$AGENT_PROXY_NAME" >/dev/null 2>&1

    # An allowlist next to the key file wins over the one baked into the image,
    # so you can edit one file and restart the proxy instead of rebuilding.
    local listmount=()
    [ -f "$AGENT_ROOT/allowlist" ] && listmount=(
        --mount "type=bind,src=$AGENT_ROOT/allowlist,dst=/etc/tinyproxy/allowlist,ro" )

    "$AGENT_ENGINE" run -d --name "$AGENT_PROXY_NAME" \
        --network "${AGENT_NET}:ip=${AGENT_PROXY_IP}" \
        --network "$AGENT_OUTER_NET" \
        "${listmount[@]}" \
        --read-only \
        --cap-drop ALL \
        --security-opt no-new-privileges \
        --pids-limit 64 \
        --memory 128m \
        "$AGENT_PROXY_IMAGE" >/dev/null || {
            printf 'oc: could not start the egress proxy. Build it with:\n' >&2
            printf '    podman build -f Dockerfile.proxy -t %s .\n' "$AGENT_PROXY_IMAGE" >&2
            printf 'or set AGENT_EGRESS=open to run without it.\n' >&2
            return 1
        }
}

# Everywhere the agent has tried to go, allowed or refused. Leave it running in
# a second pane while you work -- it is the most interesting window you have.
oc-proxy-log() { "$AGENT_ENGINE" logs -f "$AGENT_PROXY_NAME"; }

oc-proxy-down() {
    "$AGENT_ENGINE" rm -f "$AGENT_PROXY_NAME" >/dev/null 2>&1
    "$AGENT_ENGINE" network rm "$AGENT_NET" >/dev/null 2>&1
    echo "egress proxy and network removed"
}

# -----------------------------------------------------------------------------
oc() {
    local key ttyflag netargs=() extra=()

    # zsh does not word-split unquoted parameters; bash does. Be explicit.
    if [ -n "$AGENT_RUN_ARGS" ]; then
        if [ -n "${ZSH_VERSION:-}" ]; then extra=(${=AGENT_RUN_ARGS})
        else                               extra=($AGENT_RUN_ARGS); fi
    fi

    if [ ! -r "$AGENT_KEYFILE" ]; then
        printf 'oc: cannot read API key at %s\n' "$AGENT_KEYFILE" >&2
        return 1
    fi
    key="$(tr -d '[:space:]' < "$AGENT_KEYFILE")"
    [ -n "$key" ] || { printf 'oc: key file is empty\n' >&2; return 1; }

    # Handing over your whole home directory would undo the entire sandbox.
    if [ "$PWD" = "$HOME" ]; then
        printf 'oc: refusing to mount $HOME as the workspace; cd into a project first\n' >&2
        return 1
    fi

    case "$AGENT_EGRESS" in
        proxy)
            oc-proxy-up || return 1
            netargs=(
                --network "$AGENT_NET"
                --dns none
                --env "HTTPS_PROXY=http://${AGENT_PROXY_IP}:8888"
                --env "HTTP_PROXY=http://${AGENT_PROXY_IP}:8888"
                --env "https_proxy=http://${AGENT_PROXY_IP}:8888"
                --env "http_proxy=http://${AGENT_PROXY_IP}:8888"
            ) ;;
        open) netargs=() ;;
        none) netargs=(--network none) ;;
        *)    printf 'oc: AGENT_EGRESS must be proxy, open or none\n' >&2; return 1 ;;
    esac

    # Interactive TUI when attached to a terminal, pipe-friendly otherwise.
    ttyflag="-i"; [ -t 0 ] && [ -t 1 ] && ttyflag="-it"

    CSCS_INFERENCE_API_KEY="$key" \
    "$AGENT_ENGINE" run --rm "$ttyflag" \
        --env CSCS_INFERENCE_API_KEY \
        --env TERM \
        "${netargs[@]}" \
        --mount type=bind,src="$AGENT_ROOT/home",dst=/home/agent \
        --mount type=bind,src="$PWD",dst=/workspace \
        --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g,mode=1777 \
        --read-only \
        --cap-drop ALL \
        --security-opt no-new-privileges \
        --pids-limit 512 \
        --memory 4g \
        --cpus 2 \
        "${extra[@]}" \
        "$AGENT_IMAGE" "$@"
}

# Quick check that the pieces are in place, without starting the agent.
oc-doctor() {
    local ok=0
    printf 'engine    : %s\n' "$("$AGENT_ENGINE" --version 2>&1 | head -1)"
    printf 'image     : ' ; "$AGENT_ENGINE" image exists "$AGENT_IMAGE" \
        && echo "$AGENT_IMAGE" || { echo "MISSING ($AGENT_IMAGE)"; ok=1; }
    printf 'proxy img : ' ; "$AGENT_ENGINE" image exists "$AGENT_PROXY_IMAGE" \
        && echo "$AGENT_PROXY_IMAGE" || { echo "MISSING ($AGENT_PROXY_IMAGE)"; ok=1; }
    printf 'key file  : ' ; [ -r "$AGENT_KEYFILE" ] \
        && echo "readable" || { echo "MISSING ($AGENT_KEYFILE)"; ok=1; }
    printf 'home mount: ' ; [ -d "$AGENT_ROOT/home" ] \
        && echo "$AGENT_ROOT/home" || { echo "MISSING ($AGENT_ROOT/home)"; ok=1; }
    printf 'egress    : %s\n' "$AGENT_EGRESS"
    return $ok
}
# -----------------------------------------------------------------------------
