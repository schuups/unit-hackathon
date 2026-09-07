# Sandboxing an agent - Running one safely on your laptop

The goal is not a timid agent. It is a box small enough that you can stop
reading every command before approving it.

By the end you will type `oc` in any project directory and land in an OpenCode
session that:

- runs as an unprivileged user, not root;
- has a **home directory of its own**, bind-mounted from a host directory that is
  not your `$HOME` — no SSH keys, no shell history, no cloud credentials;
- has a **`/tmp` of its own** — RAM-backed, discarded on exit, never touching the
  host's temporary space;
- has a **read-only root filesystem**, so the only writable paths are ones you
  chose;
- sees **exactly one project**: the directory you were standing in;
- and can open a connection to **two hostnames**, because it has no route to
  anywhere else.

Everything below is a starting point. Once it runs, take it apart.

```
~/agent-sandbox/                 on the host — created by you, owned by you
├── home/          ──────────▶   /home/agent    (rw)  agent state: sessions, caches
└── secrets/
    └── cscs-api-key ────────▶   injected as an environment variable, never mounted

$PWD (the project you cd'd into) ──▶ /workspace  (rw)  the only code it can touch
                                 ──▶ /tmp   (tmpfs, in RAM, gone on exit)
                                 ──▶ everything else: read-only

network ─────────────────────────▶  an internal bridge with no gateway, and one
                                    allowlisting proxy sitting on it
```

What is in this directory:

| File | |
|---|---|
| `Dockerfile` | the agent image: opencode + a short tool list + the CSCS config |
| `Dockerfile.proxy` | the egress proxy image: Alpine + tinyproxy + the allowlist |
| `egress-allowlist` | the hosts the agent is allowed to reach. Two lines by default |
| `oc.sh` | the `oc` shell function and its helpers. Copy to `~/agent-sandbox/` |
| `verify.sh` | asserts every security claim below by running the container |

## 0. Prerequisites

**Podman** (used throughout) or **Docker** — every command here works with
either, substituting the binary name, *except* the egress network in step 5,
which is Podman-only as written and says so. On macOS, Podman needs its VM
running:

```bash
podman machine start          # once per reboot; `podman machine list` to check
```

You also need a CSCS account and a project with an **inference resource**. If
your project has none, the PI or Deputy PI creates it first: SwissAI projects can
self-serve in the project management portal, others need a CSCS Service Desk
ticket.

## 1. Get a CSCS inference API key

1. Go to <https://ui.inference.cscs.ch/login> and sign in with CSCS credentials.
2. Expand your project's inference resource.
3. Click **Add Key** and give it an alias that says where it lives, e.g.
   `opencode-sandbox-laptop`.
4. Optionally set a token budget, a reset period, or restrict it to specific
   models. For a training key, set a small budget — it is a hard ceiling on what
   a runaway loop can spend.
5. **Copy the key now.** It is shown exactly once.

Keys are per-person and revocable. If one leaks, delete it in the same UI and
issue a new one.

## 2. Create the sandbox directories

```bash
mkdir -p ~/agent-sandbox/home ~/agent-sandbox/secrets
chmod 700 ~/agent-sandbox/secrets
```

`home/` fills with OpenCode's state — session database, logs, the model catalogue
and provider SDK it downloads. It is disposable: delete it and the next run
starts clean.

There is deliberately no `workspace/` directory. The workspace is whatever
project you are standing in when you invoke the agent.

## 3. Store the key

Write the **raw key, nothing else** into a file — the command in step 5 reads it
from there:

```bash
umask 077
printf '%s' 'paste-your-key-here' > ~/agent-sandbox/secrets/cscs-api-key
chmod 600 ~/agent-sandbox/secrets/cscs-api-key
```

Never commit it. If you use `pass`, `1password-cli` or `direnv`, generate this
file from there instead of typing the key in.

## 4. Build the two images

```bash
cd 01-sandboxing

podman build -t opencode-cscs:1.18.17 .                      # the agent
podman build -f Dockerfile.proxy -t agent-egress-proxy:1 .   # its only way out
```

On **Linux**, add `--build-arg AGENT_UID="$(id -u)" --build-arg AGENT_GID="$(id -g)"`
to the first build so files the agent writes come back owned by you. On
**macOS**, leave them off: ownership is remapped by the VM anyway, and macOS's
default GID of `20` collides with Alpine's existing `dialout` group, which
quietly drops the agent user into that group instead of its own.

The agent image starts from `ghcr.io/anomalyco/opencode:1.18.17` — a pinned
official image holding just the `opencode` binary on a bare Alpine rootfs — and
adds `bash`, `git`, `curl`, `jq`, a terminfo database, CA certificates and the
CSCS provider config. Nothing else; see [Trimming the image](#trimming-the-image)
for what came out and why.

Need a language runtime? Do not edit the `apk add` line:

```bash
podman build --build-arg EXTRA_PACKAGES="python3 py3-pip" -t opencode-cscs:1.18.17 .
```

The second image is a ~10 MB Alpine with `tinyproxy` on it. That is the subject
of the next step.

## 5. Restrict where it can connect

The filesystem sandbox bounds what the agent can **read and write**. By itself it
says nothing about what the agent can **send**, and for a prompt injection or a
poisoned dependency that is the half that matters: the damaging move is rarely
deleting your files, it is posting them somewhere.

Two containers:

```
   internal network — no gateway                    a normal network
 ┌───────────────────────────────┐
 │  the agent container          │
 │    no default route           │
 │    no /etc/resolv.conf        │──┐  the only address it can reach
 │    HTTPS_PROXY=10.89.7.2:8888 │  │  on the entire network
 └───────────────────────────────┘  ▼
                          ┌──────────────────┐   ✓ api.inference.cscs.ch
                          │   agent-proxy    │──▶ ✓ models.opencode.ai
                          │   tinyproxy      │
                          │   allowlist      │   ✗ 403 for everything else
                          └──────────────────┘
```

The agent joins a network created with `--internal`, which gives the bridge no
gateway. This is not a rule the agent could be talked around or a variable it
could unset: inside that container the kernel has **no route to any address
outside the /24**. `--disable-dns` takes the resolver off that network as well,
and `--dns none` leaves the container with no `/etc/resolv.conf` at all, so it
cannot turn a name into an address even if it had somewhere to send the packet.

One container on that bridge — the proxy — is also attached to a normal network,
and is therefore the only way out. It runs `tinyproxy` with `FilterDefaultDeny`,
so it forwards only to the hosts named in `egress-allowlist` and answers
everything else with `403`. `ConnectPort 443` limits the tunnels it will open to
HTTPS, so there is no CONNECT to an SSH port or a database.

The proxy is what does the name resolution, which is what makes the allowlist
bite: the agent has to hand it a hostname, and that hostname is what gets
matched.

### The allowlist

`egress-allowlist` in this directory, one fnmatch pattern per line:

```
api.inference.cscs.ch
models.opencode.ai
#github.com
#registry.npmjs.org
```

Blank lines and `#` comments are ignored — and safely so: an fnmatch pattern is
matched against the whole hostname, and no hostname contains a `#` or a space, so
a commented line can never match anything. (Checked: with `#example.com` in the
file, `example.com` is refused.)

Edit it and rebuild the proxy image — a second or two, the `apk` layer is cached:

```bash
podman build -f Dockerfile.proxy -t agent-egress-proxy:1 .
oc-proxy-down && oc            # pick up the new image
```

Or skip the rebuild entirely while you experiment: `oc.sh` mounts
`~/agent-sandbox/allowlist` over the baked-in one if that file exists, so

```bash
cp 01-sandboxing/egress-allowlist ~/agent-sandbox/allowlist
$EDITOR ~/agent-sandbox/allowlist
oc-proxy-down && oc
```

is the whole edit-and-retry loop. Fold the result back into `egress-allowlist`
and rebuild once you are happy, so the image stays the source of truth.

Wildcards work: `*.githubusercontent.com` matches the subdomains and not the
apex, so you still have to list `github.com` separately if you want it.

Two entries are enough for the agent to work. Everything else is a decision you
get to make deliberately — and each one is a hole you are choosing to open.
`github.com` is the interesting example: allowing it lets the agent clone
dependencies, and also gives it somewhere to push your source.

### Watch it

```bash
oc-proxy-log
```

Every request the agent makes, allowed or refused, with the hostname:

```
CONNECT  Request (file descriptor 4): CONNECT api.inference.cscs.ch:443 HTTP/1.1
CONNECT  Established connection to host "api.inference.cscs.ch"
NOTICE   Proxying refused on filtered domain "registry.npmjs.org"
```

Left running in a second pane, that is the most informative window you have —
it is the list of everywhere the agent decided to go.

### What this stops, and what it does not

**It stops** the agent reaching a destination you did not choose. No posting the
workspace to a pastebin, no `curl … | sh` from a host someone put in a README,
no cloud metadata endpoint, no scanning the rest of your laptop or the office
network, no `pip install` from PyPI unless you allow it. That last one is a real
cost, not a free win: an agent that cannot install packages is less useful, and
you will feel it.

**It does not** make the channel confidential. Everything in the context already
goes to `api.inference.cscs.ch` by design — that is what an agent is. Code
running in the container can put whatever it likes into a request to an
allowlisted host. The allowlist shrinks the set of destinations to ones you have
decided to trust; it does not stop a determined exfiltration through one of them.

**It does not inspect TLS.** The proxy matches the hostname in the `CONNECT` and
nothing else. Whoever controls DNS for an allowed name, or an allowed host that
forwards on, is through it.

**The bridge gateway is the host.** `10.89.7.1` is an interface on the machine
running the containers. Nothing listens on it in the podman VM on macOS (checked
— every port probed refused), but under rootful Podman on Linux a service bound
to `0.0.0.0` on the host would be reachable from this "internal" network. Check
before you assume otherwise.

**Verified on Podman 5.6.2 on macOS, and only there.** Docker's
`network create` has no `--disable-dns`, and Docker puts its own embedded
resolver at `127.0.0.11` into containers on user-defined networks — on an
internal network that resolver has nothing upstream to forward to, which is
exactly the trap we hit with Podman (see the troubleshooting table). Whether
passing `--dns` to the proxy is enough to get round it under Docker, we have not
tested: there is no Docker on the machine this was built on. Treat step 5 as
Podman-only until someone checks. Everything else in this README is
engine-agnostic.

### Turning it off

```bash
AGENT_EGRESS=open oc      # the engine's normal bridge; the agent can reach anything
AGENT_EGRESS=none oc      # no network at all
```

`none` is worth running once. The TUI comes up, the model does not answer, and
the reason is that the model was never in the box — it is a web service, and the
box is the client. Nothing else about the agent changes.

## 6. Set up the `oc` command

This is the piece you will actually use. It reads the key from the file, brings
the egress network and its proxy up if they are not already, injects the key
into the container, mounts the current directory as the workspace, and forwards
any arguments to `opencode`.

It ships as [`oc.sh`](oc.sh) in this directory. Copy it out of the repository so
your shell does not depend on a checkout, then source it from `~/.zshrc` (or
`~/.bashrc`) and open a new shell:

```bash
cp 01-sandboxing/oc.sh ~/agent-sandbox/oc.sh

echo '[ -f "$HOME/agent-sandbox/oc.sh" ] && source "$HOME/agent-sandbox/oc.sh"' >> ~/.zshrc
```

Read it before you source it — it is about 120 lines and there is nothing in it
you should have to take on trust. Four things it defines:

| | |
|---|---|
| `oc` | run the agent in the current directory |
| `oc-proxy-log` | follow the egress log — everywhere the agent has tried to go |
| `oc-proxy-down` | remove the proxy and its network |
| `oc-doctor` | check images, key file and mounts without starting anything |

And the settings at the top, all overridable from your environment:

```bash
AGENT_ROOT      ~/agent-sandbox         where home/ and secrets/ live
AGENT_KEYFILE   $AGENT_ROOT/secrets/cscs-api-key
AGENT_IMAGE     opencode-cscs:1.18.17
AGENT_ENGINE    podman                  or: docker
AGENT_EGRESS    proxy                   or: open, none    (see step 5)
AGENT_RUN_ARGS  ""                      extra engine flags, e.g. --userns=keep-id
```

Two details in there worth calling out.

**The key never appears in an argument list.** The function puts it in the
**environment** of the `podman` process and passes a bare
`--env CSCS_INFERENCE_API_KEY` with no `=`, which tells the engine to forward
the value from its own environment. `--env CSCS_INFERENCE_API_KEY="$key"` would
work too, but it would put your secret where `ps` shows it to anyone else on the
machine. On a shared login node that matters.

**It is a shell function, not an alias**, so it can validate the key file, refuse
to mount `$HOME` as the workspace, and start the proxy. An alias can do none of
those.

### Using it

```bash
cd ~/git/my-project

oc                                              # interactive TUI session
oc run "add a test for the retry path"          # one-shot, non-interactive
oc --model cscs/swiss-ai/Apertus-v1.5-70B       # TUI with a different model
oc models                                       # list available models
oc --help
```

Everything after `oc` goes straight to `opencode` inside the container.

### What each flag is doing

| Flag | Why it is there |
|---|---|
| `--rm` | The container is disposable. All durable state is in the bind mounts. |
| `-it` | OpenCode is a TUI; it needs a terminal. |
| `--env CSCS_INFERENCE_API_KEY` | Forwards the key from the environment, not the command line. |
| `--env TERM` | Passes your terminal type so colours and keys behave. |
| `--mount .../home/agent` | The agent's home — **not** yours. Sessions and caches persist here. |
| `--mount "$PWD" → /workspace` | The only host code the agent can read or write. |
| `--tmpfs /tmp:rw,exec,…,size=1g` | Private, RAM-backed `/tmp`, capped at 1 GiB, destroyed on exit. `exec` and `size` are both deliberate — see below. |
| `--read-only` | Immutable root filesystem. Only `/home/agent`, `/workspace`, `/tmp` are writable. |
| `--cap-drop ALL` | Removes every Linux capability. A coding agent needs none. |
| `--security-opt no-new-privileges` | Blocks escalation via setuid binaries. |
| `--pids-limit 512` | A fork bomb, accidental or not, cannot take the host down. |
| `--memory` / `--cpus` | Caps what a runaway build or test loop can consume. |
| `--network agent-egress` | The internal bridge. No gateway, so no route off it. |
| `--dns none` | No `/etc/resolv.conf`. The container cannot resolve a name itself. |
| `--env HTTPS_PROXY=…` | Points everything at the allowlisting proxy, the one address it can reach. |

> **On the `--tmpfs` options.** Docker documents its `--tmpfs` defaults as
> `rw,noexec,nosuid,size=65536k`. Podman is not the same, and we checked rather
> than assumed: on Podman 5.6.2 a bare `--tmpfs /tmp` mounts
> `rw,nosuid,nodev,relatime` — **exec is allowed and the size is unbounded**
> (a tmpfs then defaults to half of RAM). So the two options are doing different
> jobs on the two engines. `exec` is a necessary override on Docker and a no-op
> on Podman; `size=1g` is a necessary cap on Podman and a necessary *raise* on
> Docker, where 64 KiB would break the first thing the agent tried.
>
> The reason not to leave `noexec` in place where it is the default: agents
> write-then-run things in `/tmp` constantly — build scripts, test harnesses,
> native extensions compiled during `pip install` — and the failure surfaces as a
> bare `Permission denied` that is genuinely painful to diagnose. Passing `exec`
> makes it a visible choice. Drop it once you know your toolchain does not need
> it: a real tightening, just not a free one. `verify.sh` asserts both halves.

> **Rootless Podman on Linux:** your host UID maps to container UID 0, so a
> container process running as `agent` writes to the bind mounts as an unrelated
> subordinate UID. Add `--userns=keep-id` to the function and build with the
> `AGENT_UID`/`AGENT_GID` args from step 4. On macOS the VM handles the remapping
> and neither is needed.

## 7. First run

Two things happen once and never again:

1. **OpenCode populates its caches.** It pulls the model catalogue (a ~4 MB
   `models.json`) from `models.opencode.ai` at startup. It lands under
   `/home/agent` and persists in your `home/` mount.
2. **OpenCode creates its state directories** — `.config`, `.cache`,
   `.local/share` (the session database), `.local/state`. Every path it writes to
   is pinned there by the `XDG_*` variables in the Dockerfile, which is exactly
   what makes `--read-only` workable: one bind mount captures all agent state.

You should **not** need to run `/connect` — the key arrives through the
environment and the baked config picks it up with `{env:CSCS_INFERENCE_API_KEY}`.

### The provider SDK, and why it is not a problem

The config declares `"npm": "@ai-sdk/anthropic"`, and an earlier draft of this
README warned that the container therefore needed `registry.npmjs.org` reachable
on the first message. That turns out to be wrong, and it is worth knowing why
before you widen the allowlist for it.

OpenCode 1.18.17 does ask npm for that package — you can watch it try, in
`oc-proxy-log` — but it does not need the answer. Every `@ai-sdk/*` provider
package is compiled into the `opencode` binary, and it falls back to the built-in
copy. Run with npm blocked and the request still goes out and comes back with a
`401` for the bad key, not a network error. `verify.sh` asserts exactly this, so
you will find out if a future version changes its mind.

So there is nothing to pre-warm, and `registry.npmjs.org` stays commented out in
`egress-allowlist`. If you add a provider whose SDK genuinely is not bundled, you
will need that line — and you will see the failure in the proxy log rather than
having to guess.

## 8. Check it works

### Check the sandbox

Every claim this README makes about the container is asserted by
[`verify.sh`](verify.sh), by running the container and looking rather than by
reading the flags back. It needs no API key — where one is required at all it
uses a deliberately invalid one, and being turned away by the endpoint *is* the
assertion. It takes about ten seconds and exits non-zero if anything does not
hold.

```bash
cd 01-sandboxing
./verify.sh                 # everything, including the egress tests
./verify.sh --no-network    # filesystem and privilege only
./verify.sh --build         # (re)build both images first
```

```
2. Identity, privilege and the filesystem
  ✓ runs as uid 1000, not root
  ✓ NoNewPrivs is set
  ✓ CapEff is all zeros (no capabilities)
  ✓ / is not writable                     ✓ /home/agent is writable
  ✓ /etc is not writable                  ✓ /workspace is writable
  ✓ /usr is not writable                  ✓ /tmp is writable
  ✓ /opt is not writable                  ✓ /tmp is a tmpfs (in RAM, gone on exit)
  ✓ a script written to /tmp can be executed
  ✓ ssh client present (and, per section 3, with nowhere to go)
  ✓ python3 present; requests, yaml and pytest importable
  ✓ the host's home is not visible

3. Network egress
  ✓ the container has no default route
  ✓ the container has no DNS resolver of its own
  ✓ a direct connection to the internet fails
  ✓ api.inference.cscs.ch is reachable via the proxy (401 = rejected key, not blocked)
  ✓ an unlisted host is refused by the proxy
  ✓ CONNECT to a port other than 443 is refused

39 checks, all passed.
```

Change a flag in `oc.sh` and run it again — the point of the script is that it
tells you what you actually built, not what you meant to build.

### Check your key

```bash
CSCS_INFERENCE_API_KEY="$(tr -d '[:space:]' < ~/agent-sandbox/secrets/cscs-api-key)" \
podman run --rm --env CSCS_INFERENCE_API_KEY \
  --entrypoint sh opencode-cscs:1.18.17 -c \
  'curl -sS https://api.inference.cscs.ch/v1/models \
     -H "Authorization: Bearer $CSCS_INFERENCE_API_KEY" | jq -r ".data[].id"'
```

That prints the model ids. A `401` means the key is wrong, expired, or restricted
to models you did not ask for. (Note this one runs on the normal network, so it
tests the key and not the egress path.)

Then, in a real project:

```bash
cd ~/git/some-project
oc run "Summarise what this project does, based on the files present."
```

---

## Customising

### Pick a different model

All ten CSCS models are pre-declared in the image:

| Config id |
|---|
| `cscs/moonshotai/Kimi-K2.7-Code` **(default)** |
| `cscs/zai-org/GLM-5.2` |
| `cscs/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16` |
| `cscs/google/gemma-4-31B-it` |
| `cscs/swiss-ai/Apertus-v1.5-70B` |
| `cscs/swiss-ai/Apertus-v1.5-70B-thinking` |
| `cscs/swiss-ai/Apertus-v1.5-8B` |
| `cscs/swiss-ai/Apertus-v1.5-8B-thinking` |
| `cscs/swiss-ai/Apertus-70B-Instruct-2509` |
| `cscs/swiss-ai/Apertus-8B-Instruct-2509` |

Per run with `oc --model <id>`, mid-session with `<leader>m` in the TUI, or
permanently by editing `"model"` in the Dockerfile's config block and rebuilding.

Only Kimi K2.7-Code has a documented context limit in the CSCS docs, so it is the
only one shipped with a `limit` block; the rest fall back to OpenCode's defaults.
If you settle on another, look its real context window up at
<https://ui.inference.cscs.ch/pricing> and add a `limit` — OpenCode uses it to
decide when to compact a conversation.

### Change the configuration without rebuilding

The config path is an environment variable, so you can shadow it. Add to the
function:

```bash
  --mount type=bind,src="$AGENT_ROOT/opencode.jsonc",dst=/opt/opencode/opencode.jsonc,ro \
```

Useful while experimenting; fold the result back into the Dockerfile once you are
happy, so the image stays the source of truth.

### Permission defaults

The shipped config:

```jsonc
"permission": {
  "edit": "allow",
  "bash": "allow",
  "webfetch": "ask",
  "external_directory": "ask"
}
```

**The recommendation is to keep `allow` — but notice that it now has to be
earned.** The old justification was "the container is the boundary", which was
asserted rather than demonstrated: before step 5 the agent could write only to
the workspace but could still send its contents anywhere. With the egress
allowlist in place you can point at both halves:

- the only host directory it can write is the one you were standing in;
- the only hosts it can reach are the ones in `egress-allowlist`.

Against that, an approval prompt adds little and costs a lot. **A prompt you
answer two hundred times a day is not a control, it is a reflex** — and the one
that mattered goes past at the same speed as the other hundred and ninety-nine.
That is a security argument for `allow`, not a convenience one.

**What `allow` does not cover.** Exactly one thing, and it is real: *uncommitted
work in the workspace*. `--read-only` protects everything except the directory
you deliberately made writable. The mitigation is not a prompt:

```bash
git add -A && git commit -m wip      # before you start
git diff HEAD                        # after, to see what it actually did
```

Reading the diff is a better review than approving `bash` calls one at a time,
because you are reading the result rather than predicting it.

**Flip both to `"ask"` when:**

- the workspace holds anything you cannot reproduce — uncommitted work, generated
  data, a `.env` with real credentials;
- you are running `AGENT_EGRESS=open`, which removes half the argument above;
- you mount more than one directory, or anything that is not a project.

**Why `webfetch` stays at `"ask"`.** It is the tool most likely to pull
attacker-controlled text into the context — the prompt-injection route from
Part 1 — and it fires rarely enough that reading the URL costs nothing. With the
proxy in front it can only reach allowlisted hosts anyway, so this is a second
lock on a door that is already shut.

**The middle option, and why it is weaker than it looks.** OpenCode accepts
per-pattern bash rules:

```jsonc
"bash": { "*": "allow", "git push*": "ask", "rm *": "ask" }
```

That is a reasonable speed bump on a handful of irreversible commands. Do not
mistake it for a control. It is a string match against a shell command, and there
are unlimited ways to write the same command that it will not match — `$(echo
rm) -rf`, a script written to `/tmp` and executed, `python -c`. It buys you a
moment to think when the agent does the obvious thing, and nothing at all against
anything trying to get past it. Full key list in the
[permissions docs](https://opencode.ai/docs/permissions/).

### Trimming the image

The `apk add` list in the Dockerfile is a capability list: everything on it, the
model can run. It holds `bash` (opencode's bash tool executes `bash`, not `sh`),
`ca-certificates`, `git`, `tini`, `curl`, `jq`, a terminfo database,
`openssh-client`, and `python3` with `pip`, `requests`, `yaml` and `pytest`.

`openssh-client` and `python3` are the two entries that add real capability
rather than convenience — busybox has neither. They are in anyway, for a
practical reason: an agent that cannot reach a remote node or run a script is one
people take *out* of the sandbox to get work done, and that is the worse outcome.

What `ssh` can actually reach under the default egress mode is nothing: there is
no route off the internal bridge, no resolver, and the proxy only accepts
`CONNECT` to `:443` on allowlisted hosts — all three asserted by `verify.sh`. It
becomes a real capability under `AGENT_EGRESS=open`, or if you deliberately point
it through the proxy with a `ProxyCommand`. Decide that on purpose.

`coreutils`, `less` and `ncurses` came out, for a duller reason — the base image
is busybox, which already provides them.

Which is the thing to understand before you trim anything else. **Busybox already
ships `wget`, `nc`, `vi`, `sed` and `awk`.** Dropping `curl` therefore removes
almost no capability: the agent still has two other ways to speak HTTP — three,
now that python3 is in — and one to open a raw socket. Removing a binary is only
a control when nothing else in the image does the same job. For network reach,
the control is the egress proxy — not the package list.

Heavier additions do not need an edit:

```bash
podman build --build-arg EXTRA_PACKAGES="py3-numpy py3-pandas make gcc" -t opencode-cscs:1.18.17 .
```

### Persist nothing

Drop the `home/` mount and add `--tmpfs /home/agent:rw,exec,size=1g`. Every run
starts from zero, at the cost of re-downloading the model catalogue each time.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Cannot connect to Podman socket` / daemon errors | `podman machine start` (macOS), or the Docker daemon is not running. |
| `oc: cannot read API key at ...` | Key file missing, wrong path, or unreadable. Check `AGENT_KEYFILE`. |
| `error: CSCS_INFERENCE_API_KEY is not set` | The key file existed but was empty. |
| `401` from the API | Key revoked, mistyped, or restricted to models you are not requesting. |
| Hangs on first message, no response | Check `oc-proxy-log`. If nothing appears there, `HTTPS_PROXY` is not reaching the container; if a `403` appears, add the host to `egress-allowlist`. |
| `403` in the proxy log for a host you need | The allowlist. Add it to `egress-allowlist`, rebuild the proxy image, `oc-proxy-down && oc`. |
| `oc: could not start the egress proxy` | The proxy image is not built: `podman build -f Dockerfile.proxy -t agent-egress-proxy:1 .` Or run `AGENT_EGRESS=open oc` to skip it. |
| Everything network fails, proxy log empty | The proxy container is gone (a `podman machine` restart drops it). `oc` restarts it; `oc-doctor` says what is missing. |
| Proxy log shows `Could not retrieve address info` | The proxy cannot resolve names — it was started on an internal network whose DNS is enabled. Recreate with `--disable-dns` (`oc-proxy-down`, then `oc`). |
| `Address already in use` / wrong subnet | Something else owns `10.89.7.0/24`. Change `AGENT_SUBNET` and `AGENT_PROXY_IP` in `oc.sh`, and the `Allow` line in `Dockerfile.proxy`. |
| `EACCES` under `/home/agent` | Host `home/` not writable by the container UID. On rootless Podman add `--userns=keep-id` and rebuild with the UID/GID build args. |
| `EROFS: read-only file system` | The agent wrote outside the three writable paths — either it is misbehaving, or you need another `--tmpfs`. |
| `Permission denied` running a script it just wrote to `/tmp` | The `exec` option was lost from the `--tmpfs` mount (Docker defaults to `noexec`; Podman does not). |
| `No space left on device` under `/tmp` | The 1 GiB tmpfs cap. Raise `size=` in the `--tmpfs` option. |
| `fatal: detected dubious ownership` | Should not happen — the image sets `safe.directory '*'` system-wide. If it does, the build skipped that layer. |
| Garbled TUI, arrow keys emit escape codes | `TERM` not forwarded. Keep `--env TERM`. |
| Responses truncate early | That model has no `limit` block; add its real context window. |

## What is still open

Honest list of what this does *not* do, after step 5:

- **No TLS inspection.** The proxy matches the hostname in the `CONNECT` and
  forwards an opaque tunnel. Data can still leave inside a request to an
  allowlisted host, and `api.inference.cscs.ch` receives your whole context by
  design. If you want content-level control you need a MITM proxy with a CA the
  container trusts, which is a much bigger commitment.
- **No seccomp profile of our own.** We take the engine's default, which is
  already restrictive. A tighter profile is possible and was not attempted.
- **The egress step is Podman-only as written.** Docker's embedded resolver gets
  in the way; see step 5.
- **The proxy is a shared, long-lived container.** Every `oc` session on the
  machine uses the same one and the same allowlist. Per-project allowlists would
  mean a proxy per project.
- **Nothing rate-limits the API key.** Set a token budget when you create the key
  — that is the only ceiling on a runaway loop.
- **The workspace is still writable.** By design, and the reason to commit before
  you start.

## References

- CSCS inference API — <https://docs.cscs.ch/services/inference/api/>
- CSCS key management — <https://ui.inference.cscs.ch/login>
- CSCS pricing and model limits — <https://ui.inference.cscs.ch/pricing>
- OpenCode configuration — <https://opencode.ai/docs/config/>
- OpenCode permissions — <https://opencode.ai/docs/permissions/>
- tinyproxy filtering — <https://tinyproxy.github.io/>
- Podman internal networks — `podman-network-create(1)`, `--internal`
