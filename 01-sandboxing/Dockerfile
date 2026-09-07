# syntax=docker/dockerfile:1
#
# OpenCode, wired to the CSCS LLM inference API, running as an unprivileged
# user inside a disposable container.
#
# The upstream image (ghcr.io/anomalyco/opencode) is a bare Alpine rootfs that
# contains the `opencode` binary, ripgrep, and nothing else. It runs as root,
# has no shell tooling, and expects you to bring your own configuration. This
# Dockerfile adds the pieces a coding agent actually needs, bakes in the CSCS
# provider configuration, and moves everything off root.
#
# Build:
#   podman build -t opencode-cscs:1.18.17 .
#
# On Linux add --build-arg AGENT_UID="$(id -u)" --build-arg AGENT_GID="$(id -g)".
#
# There is a second image, built from Dockerfile.proxy, that controls where this
# one is allowed to connect. See README.md.

ARG OPENCODE_VERSION=1.18.17

FROM ghcr.io/anomalyco/opencode:${OPENCODE_VERSION}

# Matching these to your host user means files the agent writes into the
# bind-mounted directories come back owned by you (relevant on Linux; on macOS
# the podman/Docker VM virtualises ownership and you leave the defaults alone --
# macOS's GID 20 collides with Alpine's `dialout` group).
ARG AGENT_USER=agent
ARG AGENT_UID=1000
ARG AGENT_GID=1000

# ---------------------------------------------------------------------------
# 1. Tools the agent will reach for.
#
#    This list is a capability list. Everything in it, the model can run. It is
#    deliberately short, and each entry has to earn its place:
#
#      bash            opencode's bash tool executes `bash`, not `sh`. Required.
#      ca-certificates TLS to the inference endpoint. Required.
#      git             the agent's undo button, and yours: `git diff` is how you
#                      see what it actually did to the workspace.
#      tini            PID 1: reaps the processes the agent spawns and forwards
#                      Ctrl-C to the TUI.
#      curl            not strictly needed -- but see the note below.
#      jq              a JSON parser. Reaches nothing, runs nothing.
#      ncurses-terminfo-base
#                      a terminfo database. Data, not a capability. ~350 kB, and
#                      it keeps TERM=xterm-256color meaningful for anything that
#                      consults terminfo.
#      openssh-client  ssh, scp, ssh-keygen. Busybox ships no ssh client, so this
#                      is one of the two entries here that adds a genuinely new
#                      capability rather than a more convenient one. It is in
#                      anyway, for a practical reason: an agent that cannot look
#                      at a remote node is one people take *out* of the sandbox
#                      to get work done, which is the worse outcome.
#                      Note what it can actually reach under the default egress
#                      mode: nothing. No route off the internal bridge, no
#                      resolver, and a proxy that only accepts CONNECT to :443
#                      on allowlisted hosts. It becomes a real capability under
#                      AGENT_EGRESS=open, or if you deliberately point it at the
#                      proxy with a ProxyCommand.
#      python3         the other one. The agent writes scripts constantly and
#                      falls back to shell badly when it cannot run them.
#      py3-pip         so it can install more -- though pypi.org is not on the
#                      egress allowlist, so this does nothing until you add it.
#      py3-requests    the HTTP client generated scripts reach for first.
#      py3-yaml        config files, CI definitions, k8s manifests.
#      py3-pytest      it writes tests; it should be able to run them.
#
#    Removed from an earlier version of this file, and why:
#
#      coreutils       busybox already provides the applets that matter.
#      less            busybox already provides `less`.
#      ncurses         the binaries (tput, infocmp); busybox has clear/reset.
#
#    And the thing worth understanding before you trim anything else: the base
#    image is busybox, which already ships `wget`, `nc`, `vi`, `sed` and `awk`.
#    Dropping `curl` therefore removes almost no capability -- the agent still
#    has two other ways to speak HTTP, three now that python3 is here. Removing
#    a binary is only a control when nothing else in the image does the same
#    job. For network reach, the control is the egress proxy, not the package
#    list.
#
#    Heavier things you may want, left out to keep the image small:
#      podman build --build-arg EXTRA_PACKAGES="py3-numpy py3-pandas make gcc" -t ... .
# ---------------------------------------------------------------------------
ARG EXTRA_PACKAGES=""

RUN set -eux; \
    apk add --no-cache \
        bash \
        ca-certificates \
        curl \
        git \
        jq \
        ncurses-terminfo-base \
        openssh-client \
        python3 \
        py3-pip \
        py3-requests \
        py3-yaml \
        py3-pytest \
        tini \
        ${EXTRA_PACKAGES}; \
    update-ca-certificates

# ---------------------------------------------------------------------------
# 2. An unprivileged user. The container is one layer of the sandbox; not
#    running as root is another, and they are cheap to combine.
# ---------------------------------------------------------------------------
RUN set -eux; \
    addgroup -g "${AGENT_GID}" "${AGENT_USER}" 2>/dev/null || true; \
    adduser -D -u "${AGENT_UID}" \
            -G "$(getent group "${AGENT_GID}" | cut -d: -f1)" \
            -h "/home/${AGENT_USER}" -s /bin/bash "${AGENT_USER}"; \
    mkdir -p "/home/${AGENT_USER}/.config/opencode" \
             "/home/${AGENT_USER}/.local/share/opencode" \
             "/home/${AGENT_USER}/.local/state" \
             "/home/${AGENT_USER}/.cache" \
             /workspace; \
    chown -R "${AGENT_UID}:${AGENT_GID}" "/home/${AGENT_USER}" /workspace

# The workspace is bind-mounted from the host, so its owner rarely matches the
# container user. Without this, every git command fails with "dubious ownership".
RUN set -eux; git config --system --add safe.directory '*'

# ---------------------------------------------------------------------------
# 3. The CSCS provider configuration, baked in read-only.
#
#    Adapted from https://docs.cscs.ch/services/inference/api/
#
#    It lives outside $HOME on purpose: $HOME is a bind mount you can wipe at
#    any time, and the image should still come up configured. Participants who
#    want to change it can either edit this file and rebuild, or override
#    OPENCODE_CONFIG at run time (see README.md).
# ---------------------------------------------------------------------------
COPY <<'OPENCODE_JSONC' /opt/opencode/opencode.jsonc
{
  "$schema": "https://opencode.ai/config.json",

  // Model ids are "<provider-id>/<model-id>", where <model-id> is exactly what
  // GET https://api.inference.cscs.ch/v1/models reports.
  "model": "cscs/moonshotai/Kimi-K2.7-Code",
  "small_model": "cscs/swiss-ai/Apertus-v1.5-8B",

  // The container is disposable and its root filesystem is read-only:
  // self-updating would fail, and would defeat pinning a version anyway.
  "autoupdate": false,

  // Do not push session transcripts to the public opencode share service.
  "share": "disabled",

  // SHIPPED DEFAULT: allow. This is a defensible default only because of what
  // is around it -- the workspace is the single writable host path, and egress
  // is restricted to an allowlist. The residual risk it does NOT cover is
  // uncommitted work in the workspace, so commit before you start and read
  // `git diff` after. Flip both to "ask" if the workspace holds anything you
  // cannot reproduce, or if you run without the egress proxy.
  // Reasoning and the middle option: see "Permission defaults" in README.md.
  // Key list: https://opencode.ai/docs/permissions/
  "permission": {
    "edit": "allow",
    "bash": "allow",
    "webfetch": "ask",
    "external_directory": "ask"
  },

  "provider": {
    "cscs": {
      // CSCS exposes an Anthropic-compatible endpoint at /v1/messages, so the
      // Anthropic AI SDK talks to it unchanged.
      //
      // opencode asks registry.npmjs.org for this package on the first message,
      // but it does not need the answer: @ai-sdk/anthropic is compiled into the
      // opencode binary and it falls back to the built-in copy. Verified by
      // running with npm blocked at the proxy -- see verify.sh, "npm is not
      // required". So npmjs.org stays off the egress allowlist.
      "npm": "@ai-sdk/anthropic",
      "name": "CSCS Inference",
      "options": {
        "baseURL": "https://api.inference.cscs.ch/v1",
        "systemMessageMode": "system",
        "apiKey": "{env:CSCS_INFERENCE_API_KEY}"
      },
      "models": {
        // Only Kimi K2.7-Code has documented limits in the CSCS docs; the
        // others fall back to opencode's defaults. Look the real numbers up at
        // https://ui.inference.cscs.ch/pricing and add a "limit" block if you
        // intend to use one of them seriously.
        "moonshotai/Kimi-K2.7-Code": {
          "name": "Kimi K2.7-Code",
          "limit": { "context": 262144, "output": 16384 }
        },
        "zai-org/GLM-5.2":                              { "name": "GLM-5.2" },
        "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16": { "name": "Nemotron 3 Super 120B" },
        "google/gemma-4-31B-it":                        { "name": "Gemma 4 31B Instruct" },
        "swiss-ai/Apertus-v1.5-70B":                    { "name": "Apertus v1.5 70B" },
        "swiss-ai/Apertus-v1.5-70B-thinking":           { "name": "Apertus v1.5 70B (thinking)" },
        "swiss-ai/Apertus-v1.5-8B":                     { "name": "Apertus v1.5 8B" },
        "swiss-ai/Apertus-v1.5-8B-thinking":            { "name": "Apertus v1.5 8B (thinking)" },
        "swiss-ai/Apertus-70B-Instruct-2509":           { "name": "Apertus 70B Instruct 2509" },
        "swiss-ai/Apertus-8B-Instruct-2509":            { "name": "Apertus 8B Instruct 2509" }
      }
    }
  }
}
OPENCODE_JSONC

# ---------------------------------------------------------------------------
# 4. Environment. Every path opencode writes to is pinned under $HOME so that a
#    single bind mount captures all agent state, and a read-only root
#    filesystem plus a tmpfs /tmp is enough to run.
# ---------------------------------------------------------------------------
ENV HOME=/home/${AGENT_USER} \
    XDG_CONFIG_HOME=/home/${AGENT_USER}/.config \
    XDG_DATA_HOME=/home/${AGENT_USER}/.local/share \
    XDG_STATE_HOME=/home/${AGENT_USER}/.local/state \
    XDG_CACHE_HOME=/home/${AGENT_USER}/.cache \
    OPENCODE_CONFIG=/opt/opencode/opencode.jsonc \
    TMPDIR=/tmp \
    EDITOR=vi \
    PAGER=less \
    TERM=xterm-256color

COPY <<'ENTRYPOINT_SH' /usr/local/bin/agent-entrypoint
#!/bin/sh
# Fail loudly and early rather than letting opencode start and then report an
# opaque 401 on the first message.
set -eu

if [ -z "${CSCS_INFERENCE_API_KEY:-}" ]; then
    cat >&2 <<'MSG'
error: CSCS_INFERENCE_API_KEY is not set inside the container.

Create a key at https://ui.inference.cscs.ch/login, write it to
~/agent-sandbox/secrets/cscs-api-key, and let the `oc` shell function pass it
in -- it reads the file and forwards the value with a bare
`--env CSCS_INFERENCE_API_KEY`, so the key never appears in an argument list.

See "Store the key" and "Set up the oc command" in README.md.
MSG
    exit 1
fi

exec opencode "$@"
ENTRYPOINT_SH

RUN set -eux; chmod 0755 /usr/local/bin/agent-entrypoint

USER ${AGENT_USER}
WORKDIR /workspace

# tini reaps orphaned processes the agent spawns and forwards Ctrl-C to the TUI.
ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/agent-entrypoint"]
CMD []
