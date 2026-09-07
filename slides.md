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

# SW1 Unit Hackathon

## Day-opening round-table of contributions
### Stefano Schuppli

<br>

**00** — intro to the agent application
**01** — an example of local sandboxing
**02** — development workflows
**03** — writing your own agent, in Python
**04** — AutoAlps

<!--
Shared hour, several presenters — keep it tight. 00 is the only part that needs
slides; 01 and 03 happen at the terminal.
Decks: 00-agents-introduction/ · 01-sandboxing/ · 02-workflow/ · 03-agent-example/
03 is a hand-written Python agent — deliberately not Codex, Claude Code or
opencode, to show the loop has no magic in it.
-->
