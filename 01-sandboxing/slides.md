---
marp: true
theme: default
paginate: true
size: 16:9
header: 'SW1 Unit Hackathon on Agentic possibilities'
footer: '7th September 2026, CSCS LCP'
style: |
  :root {
    --ink: #16202b;
    --muted: #5b6b7c;
    --accent: #0f6f8c;
    --warn: #b4451f;
    --rule: #d8e0e6;
    --code-bg: #f2f5f7;
  }
  section {
    font-family: "Helvetica Neue", Inter, system-ui, sans-serif;
    font-size: 25px;
    color: var(--ink);
    background: #ffffff;
    padding: 60px 70px 70px 70px;
    line-height: 1.45;
  }
  section h1 { font-size: 46px; color: var(--ink); margin: 0 0 .4em 0; letter-spacing: -.5px; }
  section h2 { font-size: 34px; color: var(--accent); margin: 0 0 .5em 0; letter-spacing: -.3px; }
  section h3 { font-size: 27px; color: var(--muted); font-weight: 600; }
  section code {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    background: var(--code-bg); padding: .08em .3em; border-radius: 4px; font-size: .92em;
  }
  section pre {
    background: var(--code-bg); border-left: 4px solid var(--accent);
    padding: 16px 20px; border-radius: 6px; font-size: 19px; line-height: 1.35;
  }
  section pre code { background: none; padding: 0; font-size: inherit; }
  section blockquote {
    border-left: 4px solid var(--warn); margin-left: 0; padding-left: 20px;
    color: var(--ink); font-style: normal;
  }
  section strong { color: var(--accent); }
  section em { color: var(--muted); font-style: italic; }
  header, footer { color: #9aa8b4; font-size: 15px; }
  section::after { color: #9aa8b4; font-size: 15px; }

  /* title + section dividers */
  section.lead, section.section {
    background: #16202b; color: #f4f7f9; justify-content: center;
  }
  section.lead h1, section.section h1 { color: #ffffff; font-size: 56px; }
  section.lead h2, section.section h2 { color: #7fc8dd; font-size: 30px; font-weight: 500; }
  section.lead strong, section.section strong { color: #7fc8dd; }
  section.lead em, section.section em { color: #a9bccb; }
  section.lead .note, section.section .note { color: #93a5b3; }
  section.lead blockquote, section.section blockquote { border-left-color: #7fc8dd; }
  section.lead code, section.section code { background: #24313f; color: #cfe6ef; }
  section.section::after, section.lead::after { color: #52616f; }

  /* two-column layout */
  section.split { display: grid; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
  .cols.wide-left { grid-template-columns: 1.35fr 1fr; }

  /* small helper classes */
  .big { font-size: 34px; line-height: 1.35; }
  .note { color: var(--muted); font-size: 21px; }
  .tag {
    display: inline-block; background: var(--warn); color: #fff; font-size: 15px;
    padding: 2px 10px; border-radius: 12px; letter-spacing: .4px; vertical-align: middle;
  }
  .tag.ok { background: var(--accent); }
  /* three-column grid + framed cards */
  .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 26px; }
  .card { border-top: 3px solid var(--accent); padding-top: 9px; font-size: 21px; }
  .card.warn { border-top-color: var(--warn); }
  .card h4 { margin: 0 0 .25em 0; font-size: 22px; color: var(--accent); font-weight: 700; }
  .card.warn h4 { color: var(--warn); }

  /* one-line lead-in under a heading */
  .lede { font-size: 23px; color: var(--muted); margin: -.35em 0 .85em 0; line-height: 1.35; }

  /* figures built from plain elements — no raw SVG, so they survive any renderer */
  .fig { margin: 12px 0 14px 0; }
  .axis { font-size: 14px; color: var(--muted); margin: 0 0 6px 92px; }
  .brow { display: grid; grid-template-columns: 80px 1fr; align-items: center;
          gap: 12px; margin-bottom: 8px; }
  .blab { font-size: 16px; color: var(--muted); text-align: right; }
  .bar { display: flex; height: 24px; }
  .bar .hist { background: #8fb9cc; }
  .bar .new { background: var(--warn); width: 4%; }
  .w0 { width: 0; } .w26 { width: 26%; } .w54 { width: 54%; } .w86 { width: 86%; }
  .legend { font-size: 14px; color: var(--muted); margin: 8px 0 0 92px; }
  .legend.ind { margin: -2px 0 12px 92px; }
  .sw { display: inline-block; width: 11px; height: 11px; margin-right: 6px; }
  .sw.h { background: #8fb9cc; } .sw.n { background: var(--warn); }

  .ttft { width: 34%; border-bottom: 1px solid #9aa8b4; text-align: center;
          font-size: 14px; color: var(--muted); padding-bottom: 3px; margin-bottom: 5px; }
  .tl { display: flex; height: 48px; font-size: 16px; }
  .tl.slim { height: 30px; font-size: 14px; }
  .tl-pre { flex: 0 0 34%; background: var(--accent); color: #fff;
            display: flex; align-items: center; justify-content: center; letter-spacing: .5px; }
  .tl-pre.cold { flex: 0 0 52%; }
  .tl-pre.warm { flex: 0 0 5%; }
  .tl-dec { flex: 1; color: #2f6b55; display: flex; align-items: center;
            justify-content: center; letter-spacing: .5px;
            background: repeating-linear-gradient(90deg, #7fbfa3 0 14px, #ffffff 14px 22px); }
  .chip { background: #ffffff; color: #2f6b55; padding: 3px 10px; letter-spacing: .5px; }
  .tlcap { display: flex; font-size: 14px; color: var(--muted); margin-top: 5px; }
  .tlcap .c1 { flex: 0 0 34%; text-align: center; }
  .tlcap .c2 { flex: 1; text-align: center; }

  /* email mock-up */
  .mail { border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; font-size: 19px; }
  .mail-hdr { background: #eef3f6; padding: 7px 13px; border-bottom: 1px solid var(--rule);
              color: var(--muted); font-size: 15px;
              font-family: ui-monospace, Menlo, monospace; }
  .mail-body { padding: 11px 13px; line-height: 1.4; }
  .ghost { color: #fefefe; }
  .reveal { display: block; margin: 8px 0; background: #fdeeea; color: var(--warn);
            border-left: 3px solid var(--warn); padding: 8px 11px;
            font-family: ui-monospace, Menlo, monospace; font-size: 16px; line-height: 1.4; }
  .caption { font-size: 17px; color: var(--muted); margin-top: 7px; }

  section.tight li { margin-bottom: .15em; }
  section.tight { font-size: 23px; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# Sandboxing a coding agent

## Bounding what it can read, write, and reach
### Stefano Schuppli et al.

<br>

<span class="note">Stock container primitives — rootless Podman, an unprivileged user, a read-only root, no route out except one allowlisted proxy. Pointed at CSCS inference, not a vendor endpoint.</span>

---

## What we are going to set up

<p class="lede">Two container images and one shell command. After that, a coding agent that can only touch the project you started it in.</p>

Type `oc` in any project and land in an OpenCode session that:

- runs as an **unprivileged user**, not root
- has a **home of its own** — `~/agent-sandbox/home`: no SSH keys, no cloud creds. One home shared by every session, so history and caches persist
- has a **`/tmp` of its own** — RAM-backed, gone on exit
- has a **read-only root filesystem**
- takes **one project as its workspace** — the directory you started it in; nothing else of yours is mounted
- reaches only what an **allowlist you control** permits — there is no other route off its network

<span class="note">Small enough that you can stop reading every command before you approve it.</span>

---

## What the box looks like

<p class="lede">Two containers: the agent, and the only thing it is allowed to talk to.</p>

```
  HOST                        AGENT CONTAINER                   EGRESS CONTAINER
  ────────────────────        ────────────────────────────      ──────────────────
  ~/agent-sandbox/
    home/            ──────▶  /home/agent   rw  agent state
    secrets/api-key  ─env──▶  injected, never mounted
  $PWD (one project) ──────▶  /workspace    rw  the only code

                              /tmp   tmpfs, RAM, gone on exit
                              /      the image's own rootfs, --read-only
                              the host's other paths: not mounted, so not there

                              no default route, no resolver
                              HTTPS_PROXY ──────────────────▶  tinyproxy + allowlist
                                                                 ✓ hosts on the list
                              internal bridge — no gateway       ✗ all else, 403 + log
```

<span class="note">There is no default route in that container at all, and the proxy does the name resolution.</span>

---

## Building it

<p class="lede">Two one-off steps: get a key, build two images.</p>

```bash
# 1. a key from https://ui.inference.cscs.ch/login  (shown once — set a budget)
umask 077
printf '%s' 'your-key' > ~/agent-sandbox/secrets/cscs-api-key

# 2. build — the agent, and the only thing it is allowed to talk to
podman build -t opencode-cscs:1.18.17 .
podman build -f Dockerfile.proxy -t agent-egress-proxy:1 .
```

> The `apk add` list is a capability list — everything on it, the model can run.
> `openssh-client` and `python3` are on it on purpose: an agent that cannot ssh to a
> node or run a script gets used *outside* the sandbox instead.
> **Reach is bounded by the proxy, not by the package list.**

---

<!-- _class: tight -->

## The `oc` command

<p class="lede">Read it first as an alias: one word standing in for a long <code>podman run</code>.</p>

```bash
# the shape of it
alias oc='podman run --rm -it  …about twenty flags…  opencode-cscs:1.18.17'
```

It ships as a shell **function**, not an alias, because three things must happen first:

- read the key from a file and pass it in the **environment**, never in an argument list where `ps` would show it
- **refuse to start** if you are sitting in your `$HOME` — that would hand over everything
- bring the egress proxy up if it is not already running

```bash
oc                                       # interactive TUI
oc run "add a test for the retry path"   # one-shot, no TUI
AGENT_EGRESS=none oc                     # same, but with no network at all
oc-proxy-log                             # live: everywhere it tried to go
oc-doctor                                # is everything in place?
```

---

<!-- _class: tight -->

## The allowlist — which hosts it can reach

<p class="lede">One file. Every line is a hostname the proxy will forward to; anything else gets a 403 and a log entry.</p>

```
# egress-allowlist — one pattern per line, matched against the WHOLE hostname
api.inference.cscs.ch      # the inference endpoint — without it, nothing works
models.opencode.ai         # model catalogue, fetched at startup
#github.com                # uncomment to allow clone and fetch — and exfiltration
```

<div class="cols">
<div class="card">

#### What it stops

- posting the workspace to a pastebin
- `curl … | sh` from a host named in a README
- the cloud metadata endpoint
- scanning your laptop and the office LAN
- `pip install` — **which you will feel.** Not a free win

</div>
<div class="card warn">

#### What it does not

- **exfiltration through an allowed host.** Your whole context already goes to CSCS by design
- **TLS inspection.** It matches the hostname in the `CONNECT`, nothing more
- the bridge gateway *is* the host — check what listens there
- Docker: its embedded resolver gets in the way. Verified on Podman only

</div>
</div>

---

<!-- _class: tight -->

## Gotchas — every one found by running it

- **Matching is whole-hostname.** `theguardian.com` does not cover `www.theguardian.com`; you need `*.theguardian.com` as well. The proxy log names the exact host it refused.

- **The `--tmpfs` defaults are not what the docs led us to expect.** Docker documents `rw,noexec,nosuid,size=65536k`; Podman 5.6.2 gives `rw,nosuid,nodev` — exec **allowed**, size **unbounded**. So `exec` is an override on one engine and a no-op on the other; `size=1g` is a cap on one and a raise on the other.

- **The provider SDK does not need npm.** The config says `"npm": "@ai-sdk/anthropic"` and opencode does ask — but every `@ai-sdk/*` is compiled into the binary. Blocked at the proxy, it falls back and works.

- **Podman builds OCI by default, where `SHELL` is ignored** — silently dropping `set -e`. Use explicit `set -eux` in each `RUN`.

- **An internal network kills the proxy's own DNS too** — create it `--disable-dns` so the proxy inherits the host's resolvers instead.

---

<!-- _class: tight -->

## Take it apart <span class="tag">YOUR TURN</span>

<p class="lede">Suggested experiments, and what each one demonstrates.</p>

<div class="cols">
<div>

- **`AGENT_EGRESS`** picks the network mode: `proxy` (default), `open`, `none`.
- Run it with `none`: the TUI starts and the file tools still work, but no reply arrives. Inference runs at CSCS, not in the container.
- Add `github.com` to the allowlist, then look at what else that opens — a repo it can push to is a route your source can leave by.
- Delete a line from the `apk add` and rebuild; check what busybox still provides in its place.
- Flip `bash` from `allow` to `ask` and work for an hour. That is the trade the shipped default is making.

</div>
<div>

**Future work**

- no TLS inspection — a MITM proxy is a much bigger commitment
- one shared proxy and one allowlist per machine, not per project
- the egress step is Podman-only as written
- the workspace is still writable — **commit before you start**

</div>
</div>
