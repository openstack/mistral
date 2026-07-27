---
name: apm-authoring
description: How to author APM packages — instructions, skills, prompts, agents, hooks. Use when editing APM primitives (`apm.yml`, `*.instructions.md`, `SKILL.md`, `*.prompt.md`, `*.agent.md`, hooks) or laying out a new `agent-packages/<name>/`.
---

# Authoring APM packages

[APM](https://github.com/microsoft/apm) is a package manager for AI-agent
primitives: **instructions** (always-on rules), **skills** (on-demand
how-to guides), **prompts** (user-invoked slash-commands), **agents**
(sub-agent personas with tool boundaries) and **hooks** (lifecycle
scripts). A platform can ship its conventions as APM packages so service
developers receive them as `apm dependencies` and agents like Claude
Code, Copilot and Cursor pick them up natively.

This skill is the contract between library authors and the agents that
read their packages. Apply it whenever you touch `apm.yml`, anything
under a `.apm/` tree, or set up a new `agent-packages/<name>/`.

## Package layout

A library repo can host one or more APM packages. Each one lives under
`agent-packages/<package-name>/` so the path itself is the disambiguator:

```text
agent-packages/
└── <package-name>/                  # = `name:` in apm.yml
    ├── apm.yml
    └── .apm/
        ├── instructions/            # *.instructions.md — always-on rules
        │   └── <package-name>.instructions.md
        ├── skills/                  # SKILL.md — on-demand how-tos
        │   └── <package-name>/
        │       └── SKILL.md
        ├── prompts/                 # avoid — Codex skips prompts; use a user-invoked skill
        │   └── <name>.prompt.md
        ├── agents/                  # optional — *.agent.md, sub-agent personas
        │   └── <name>.agent.md
        └── hooks/                   # optional — lifecycle scripts
```

Rules:

- `<package-name>` is descriptive and unique (`context-propagation-go-usage`,
  `hardened-dockerfile-usage`), **not** a generic placeholder like
  `user-guide`. Multiple packages can sit side-by-side in one repo, so the
  directory name has to identify the package on its own.
- A package holds a **coherent set** of primitives (instructions,
  skills, prompts, agents, hooks) that share an audience and a
  trigger surface (e.g. `<lib>-usage` for
  day-to-day code; a separate `<lib>-troubleshooting` if the failure-mode
  catalogue is large enough to deserve its own activation). Bundle by
  topic, not by file count — a one-skill package and a five-skill package
  are both fine if each set is internally coherent.
- An **auto-triggered** skill needs a paired instructions file.
  Without the trigger merged into `AGENTS.md` / `CLAUDE.md` the agent
  has no signal to pull the skill in. Keep names aligned so the link
  is obvious from the tree. Two cases need no instruction: a small
  always-true rule may ship as a standalone instruction with no skill
  behind it (see next section), and a **user-invoked** skill — the
  replacement for a slash-command — carries its activation rule in its
  own `description:`, so the user invokes it by name and no paired
  instruction is needed (see "Agents, hooks, and prompts").

The host repo itself is also an APM project: its own AGENTS.md / CLAUDE.md
must be **rendered by `apm compile`** from a local `.apm/` package plus
declared dependencies. Do not hand-author AGENTS.md / CLAUDE.md — `apm
compile` overwrites it.

## Choosing the right primitive

APM ships five kinds of primitives. Pick the one that matches *when*
the rule needs to fire and *who* invokes it:

- **Instructions** (`*.instructions.md`) — rules merged into the
  agent's root file (`AGENTS.md` / `CLAUDE.md`) by `apm compile` and
  living in session context on every turn. Cost: tokens × every
  consumer × every turn.
- **Skills** (`SKILL.md`) — on-demand how-to guides loaded only after
  the agent decides a skill is relevant (steered by the trigger
  phrase in a paired instruction). Cost paid only when activated.
- **Prompts** (`*.prompt.md`) — slash-commands the **user** invokes
  explicitly (`/review-pr`). The primitive exists, but `apm compile`
  does not deploy it to the Codex target, so a prompt silently
  vanishes there
  ([microsoft/apm#1781](https://github.com/microsoft/apm/issues/1781)).
  For a user-invoked workflow, ship a **skill without a paired
  instruction** instead (see below): it deploys to every target, and
  the user still invokes it by name.
- **Agents** (`*.agent.md` under `agents/`) — sub-agent personalities
  with their own context window and tool-permission boundaries.
  Spawned via `Agent` / `Task`-style tools. Use when a task deserves
  its own scratch context, or the parent should not have a particular
  tool, or the work is parallelizable.
- **Hooks** (`hooks/`) — lifecycle scripts that run at specific
  points in the agent loop (pre/post tool call, on-stop, etc.). They
  do not enter the model's context at all — they execute in the
  harness. Use them for deterministic enforcement (linters, secret
  scanners, log filters) where prose advice is unreliable.

For most library-usage packages the bulk of the work is **one
instruction** (the trigger) plus **one skill** (the how-to). A
user-invoked workflow is also a skill — one without a paired
instruction, invoked by name (see "Agents, hooks, and prompts").
Agents and hooks are reserved for the two cases the instruction-skill
pair cannot cover: isolated sub-tasks and hard enforcement.

### Instruction vs skill: the common case

The decision that comes up on almost every package is whether a given
rule should ship as a persistent instruction or as a skill. Decide
for each piece of guidance:

- **Persistent (instruction)** — rules the agent should follow on
  **every turn regardless of which files are open**, plus the
  trigger phrase that names a skill. The best instructions are
  *nudges*: cases where the LLM already knows how to do the task
  but defaults to a sub-optimal flavour of it.
  - "Pass `--batch --quiet` when invoking Maven" — saves tokens
    by suppressing chatty output. The LLM already knows Maven; the
    instruction only steers the flag.
  - "Place new ADRs under `docs/adr/<NNNN>-<slug>.md`" — repo-wide
    directory convention the LLM cannot guess.
  - "Use the `gh` CLI for all GitHub operations" — picks the right
    tool regardless of what file the agent is touching.
- **On-demand (`SKILL.md`)** — anything tied to a specific file
  type, library, or task: setup checklists, multi-step how-tos,
  code templates, library-specific call patterns, failure-mode
  catalogues. The paired instruction-trigger fires only when the
  agent reaches a relevant file, so the body never pollutes
  unrelated turns (codebase exploration, bug triage, CI debugging
  on another stack). Counter-examples — these look like instruction
  material but belong in a skill:
  - "Use `logger.InfoC(ctx, …)` in `*.go` handlers" → ships in a
    `go-authoring` (or logging-specific) skill, triggered on
    `**/*.go`. Loading it on every turn would pay tokens for it
    while reading SQL, editing YAML, or reviewing CI logs.
  - "Dockerfiles use `USER 10001:10001` and `--chown=10001:0`"
    → ships in a `hardened-dockerfile-usage` skill, triggered on
    `**/{Dockerfile,Dockerfile.*,*.Dockerfile}`.

Heuristic: an instruction earns its place only if the agent
benefits from it on **every** turn, not just when working on a
specific stack. "Always true, short, *and* cross-cutting" is an
instruction; "true when working on X" is a skill triggered by X.
If an instructions file grows past a paragraph, or starts referring
to a specific language or file type, the overflow probably wants
to move into a `SKILL.md` and be replaced by a one-line trigger.

## What an instructions file is for

Two things only: a narrow `applyTo:` and a short trigger body. Both
land in the merged `AGENTS.md` / `CLAUDE.md`, so every byte costs
tokens on every turn for every consumer.

`applyTo:` is **not a reliable runtime gate**, because what it does
depends on the compile target:

- **`apm compile` to `AGENTS.md` / `CLAUDE.md`** (the dominant
  target for Claude Code, Codex, etc.) — the target format has no
  concept of per-file scoping, so once an instruction lands in the
  merged file it loads on every turn regardless of the path the
  agent is touching. APM uses `applyTo:` here only as a *placement
  heuristic*: it picks which subdirectory's root file an
  instruction goes into (e.g. `applyTo: "frontend/**/*.tsx"` may
  land in `frontend/CLAUDE.md` instead of the repo root). Best
  effort, no guarantee.
- **Native deployment to agents that read primitives directly**
  (Cursor `.cursor/rules/*.mdc`, Copilot custom-instructions) —
  `applyTo:` (or its target-native equivalent) survives into the
  deployed file and the agent runtime treats it as a real scope
  filter.

Because at least one major target cannot honour `applyTo:` as a
runtime gate, **state the file scope in the trigger sentence
itself** — "When editing `*.go` …" — so the rule fires correctly
whatever target `apm compile` produces. Don't rely on `applyTo:`
alone to gate behaviour.

Rules for the file:

- Use a narrow `applyTo:` mask (`**/*.go`,
  `**/{Dockerfile,Dockerfile.*,*.Dockerfile}`, `**/pom.xml`) so APM can
  place the instruction near the code it governs. `**/*` is fine only
  for umbrella packages where the rule really is universal.
- The body says **what the user is doing** when the skill should
  activate — a verb phrase, ideally with the file mask — not "when the
  user works with library X". The library name is bookkeeping; the
  verb is the trigger.

```markdown
---
description: Go coding standards for cross-service context propagation.
applyTo: "**/*.go"
---

When editing `*.go` and propagating request context (X-Request-Id,
X-Version, headers, etc.) between microservices, apply the
`context-propagation-go-usage` skill.
```

Avoid in the trigger:

- `When the user works with github.com/.../<long-import-path>
  library — registering providers, initializing context,
  propagating headers, writing custom providers, working with snapshots …`
  This is the skill body, not a trigger. Pick the user-facing verb.
- Negative scope (`Do NOT use for the X operator`). If a different repo
  must not pick up your skill, that repo's own scope handles it. Don't
  fight other packages from yours.
- Padding the trigger with "or reviewing code that does …". The verb
  phrase already covers both creation and review; adding the second
  half just inflates the persistent-context cost.

## What a SKILL.md is for

The skill is what the agent reads **after** it decides to engage. Its job
is to teach the agent things it cannot infer from imports, types, or
generic documentation. Three rules:

### 1. Encode platform-specific knowledge, nothing else

Include only what the agent cannot reasonably know:

- **Required ordering** of init steps (`configloader.Init` before
  `logging.GetLogger`; `serviceloader.Register` before
  `fiberserver.Process`).
- **Side-channel contracts** (env vars, `application.yaml` files that
  must exist, k8s projected volumes that must be mounted).
- **Failure modes that look fine in code** (`Process()` panics if the
  security middleware was not registered; `AllowedHeader` silently
  no-ops without `HEADERS_ALLOWED`).
- **Helpers that replace ad-hoc work** (`ctxhelper.AddSerializableContextData`
  instead of manual header copying).
- **Conventions a reviewer would otherwise have to memorize**
  (`USER 10001:10001`, `--chown=10001:0`, `appuser`).

Leave out everything else. In particular, don't include:

- Generic ecosystem knowledge — `go get`, adding to `pom.xml`, Dockerfile
  multi-stage basics, how `CGO_ENABLED=0` produces a static binary. The
  agent already knows. Stating it dilutes the signal of what is
  platform-specific.
- Material that belongs in the library's own API docs. Languages publish
  generated docs (godoc → pkg.go.dev, javadoc, rustdoc, pydoc) and the
  agent can fetch them when needed. Repeating method signatures and
  parameter prose in the skill creates a second source of truth that
  drifts.
- Implementation-detail asides ("returns an interface with level-based
  methods", "does not override GOMEMLIMIT if already set"). If the
  developer doesn't act on it, the skill doesn't need it.

### 2. One canonical example per concern

State the rule, then show one concrete example. Do not show two examples
that vary in trivial ways — a reviewer rightly asks "is this any
different from the previous example?". If a real variant exists (Quarkus
fast-jar vs Spring Boot uber-jar; net/http vs Fiber middleware), show it
once and label what makes it different.

When listing pitfalls, prefer **rule + brief reason** over a wall of
`// WRONG: …` snippets. Negative examples without the matching positive
flow leave the reader guessing what was supposed to happen. A
"Common pitfalls" section is fine — keep each entry to a one-line cause
and one-line fix.

### 3. Don't separate "create" and "review"

The skill should make the same recommendation whether the agent is
writing new code or reviewing existing code. Avoid a dedicated
"Reviewing an existing X" section that restates the same rules in
checklist form — that's two sources to keep in sync. Express the rules
once, in active voice, and let them apply to both directions.

## Agents, hooks, and prompts

`apm` supports these three primitives in addition to instructions
and skills, but day-to-day authoring on a library-usage package
rarely needs them. This skill does not restate their file formats —
fetch the [upstream `apm` documentation](https://github.com/microsoft/apm)
when you reach for one.

The rule that does belong here is about *when* to reach for them:
**the user decides whether to introduce an agent or a hook — do not
pick one unilaterally over a skill or instruction. Don't ship a prompt
at all; use a user-invoked skill (the Prompts bullet explains why).**

- **Agents** (`*.agent.md`) change the runtime shape — separate
  context budget, restricted tool set, parallelisable. Worth it
  when a sub-task is heavy enough to deserve its own scratch
  context, but not as a default. If the user has not asked for an
  agent, propose a skill first.
- **Hooks** run scripts at lifecycle events and do not enter the
  model's context. Use them for deterministic enforcement (linters,
  secret scanners, log filters) when prose advice has demonstrably
  failed. Don't pre-emptively wire a hook for "good hygiene".
- **Prompts** (`*.prompt.md`) run only when the user types the
  slash-command. Don't ship one: `apm compile` does not deploy prompts
  to the Codex target, so a package that relies on a prompt breaks
  silently for Codex users
  ([microsoft/apm#1781](https://github.com/microsoft/apm/issues/1781),
  closed as not planned). For a single-use workflow the user would
  otherwise invoke as a slash-command, write a **skill without a paired
  instruction** instead: it deploys to every target, and the user (or
  another agent) invokes it by name. Put the activation rule in the
  skill's `description:` — e.g. "Use only when the user asks to triage
  dependency PRs" — so it does not auto-fire on unrelated turns.

## Frontmatter and formatting

- YAML frontmatter starts at column 0. Do not indent its keys or content
  body. (Indented frontmatter renders as a blockquote inside `<pre>` and
  may not be parsed as frontmatter at all.)
- Use plain Markdown source for tables, lists and code fences. Do not
  paste rendered ASCII boxes (`┌──┬──┐`) — they are unreadable in the
  source view, agents process them poorly, and they don't survive edits.
- Code blocks specify the language (` ```go `, ` ```dockerfile `,
  ` ```yaml `).
- Skill `description:` is the field the agent uses to decide whether
  the skill is relevant. Make it a verb-led sentence describing the
  user task, not a feature list of the library.

## Versions

Do not hard-code library or image versions in skills.

- The repository's own `go.mod`, `pom.xml`, existing Dockerfile, etc. is
  the source of truth for the version a service uses. The skill should
  point the agent at that, not at a number that will be stale next
  quarter.
- Where the skill must mention a version (e.g., a base-image migration
  story), make it clear that the value is illustrative and direct the
  agent to the upstream release page.
- Distribution names should be precise or omitted. Don't write
  "OpenJDK" when you mean "Eclipse Temurin" or just "Java 21" — be
  specific or generic, never sloppy.

The skill itself is versioned in `apm.yml`. Bump that when the contract
changes (new required step, breaking rename), not on every prose edit.

## apm.yml

Minimal valid manifest:

```yaml
name: <package-name>           # matches agent-packages/<package-name>/
version: 1.0.0
description: One-sentence purpose.
author: <your-org>

# Optional: list other APM packages this one depends on.
dependencies:
  apm:
    - <owner>/<repo>/<path>/agent-packages/<package>#<ref>
```

Conventions for the dependency list:

- Pin to a tag (`@v1.2.0`) for stable consumers; pin to a branch
  (`#feat/agent-packages`) only while a feature is still in review.
- Each dependency line resolves to one `agent-packages/<name>/` folder,
  so the suffix in the URL must end in the package directory — never
  the repo root.

## Reference: the umbrella pattern

A platform with several libraries should expose **one umbrella** package
for service developers to depend on, plus one leaf package per library
hosted alongside that library's source. The umbrella's only job is the
dependency list and a near-empty instructions file. Don't duplicate
library content in the umbrella; transitive resolution is what makes the
model work.

## Editing a skill that came from a dependency

Local primitives — files under your repo's own `.apm/` — are free to
edit and recompile. Deployed primitives that arrived via
`apm install` (under `.github/skills/`, `.cursor/rules/`, or wherever
the runtime expects them) are **not** the source of truth: a local
edit will be overwritten the next time anyone runs `apm install`
against the lockfile.

If the user asks to fix or extend a skill that came from a
dependency:

1. Locate the upstream package via `apm_modules/`:
   - **Skills, agents, prompts** — search for the folder/file by
     its name under `apm_modules/`.
   - **Instructions** — grep `apm_modules/` for the rule's text
     (instructions get merged on compile, so name-matching does not
     help).

   The matching `apm_modules/<owner>/<repo>/.../` path tells you
   the source repo; cross-check with `apm.yml` / `apm.lock` for the
   pinned version.
1. File a PR against that repo's `.apm/<primitive-folder>/<name>/`
   (e.g. `.apm/skills/<name>/SKILL.md`).
1. Once the upstream change is released, bump the version in this
   repo's `apm.yml` and run `apm install` followed by `apm compile`.

## Common authoring pitfalls

- **Trigger sentence is a feature list.** Replace with a one-verb
  description of the user task.
- **Skill restates language docs.** Drop the prose that simply mirrors
  godoc; link or trust the agent to fetch.
- **Multiple near-identical examples.** Collapse to one and explain the
  axis of variation if a second is genuinely different.
- **Tables drawn with box-drawing characters.** Convert to Markdown
  table syntax or to a bullet list.
- **Hard-coded versions in the skill body.** Defer to the consumer's
  manifest or to the upstream release page.
- **Generic wisdom mixed with platform rules.** If a paragraph could
  appear unchanged in any tutorial on the topic, it doesn't belong here.
- **Negative-only checklists.** Pair each `WRONG` with the positive
  flow, or replace with a one-line rule plus reason.
- **`agent-packages/user-guide/` as a directory name.** Use the
  package's actual name; multiple packages collide otherwise.
- **Hand-edited AGENTS.md / CLAUDE.md in a repo that already uses
  APM.** Edit the local `.apm/` package and re-run `apm compile`.
- **Shipping a workflow as a prompt.** `apm compile` skips prompts for
  the Codex target, so the slash-command silently disappears there.
  Write a user-invoked skill (no paired instruction) instead.
