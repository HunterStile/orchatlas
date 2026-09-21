# OrchAtlas 0.1.0

This release implements a local recipe compiler and guarded installer for Codex and OpenCode. It creates native agents and a discoverable skill; the selected host executes the workflow after the user starts a session.

## Commands

All commands accept `--json`. Project commands accept `--project PATH` after the command name. The target directory must exist.

| Command | Effect |
| --- | --- |
| `recipes [--catalog FILE]` | List bundled or local workflows |
| `models [--host HOST]` | List documented model-ID examples |
| `init [--host HOST] [--recipe ID@VERSION] [--set HOST.ROLE=MODEL]` | Create `orchatlas.json`; default host is both, recipe is lean |
| `set HOST.ROLE MODEL [--effort LEVEL]` | Update a model choice |
| `use ID@VERSION [--catalog FILE] [--with-models]` | Replace recipe snapshot; explicitly opt into its model defaults |
| `validate` | Validate manifest and compile in memory |
| `preview [--diff]` | Inspect file changes without writing |
| `apply` | Apply artifacts and save an undo receipt |
| `status` | Report installation, drift and pending changes |
| `undo [--apply]` | Preview or reverse the latest applied transaction |

No command sends model requests, installs a host, changes authentication, publishes a repository or executes a task. Apply writes only fixed project-local destinations and transaction data.

## Model choices

Each enabled host has `planner`, `builder` and `reviewer` settings. The reviewer remains in the manifest for lean but is inactive: the planner/coordinator reviews the result.

```json
{
  "codex": {
    "planner": {"model": "inherit"},
    "builder": {"model": "gpt-5.6-terra", "effort": "medium"},
    "reviewer": {"model": "inherit"}
  },
  "opencode": {
    "planner": {"model": "inherit"},
    "builder": {"model": "openai/gpt-5.2", "effort": "medium"},
    "reviewer": {"model": "inherit"}
  }
}
```

This is only the `hosts` section. Run `init` for a complete manifest. `inherit` leaves the exact model/effort unpinned. OpenCode children inherit the primary model; Codex applies its own configuration precedence. Host changes can therefore change outcomes with an unchanged manifest.

An explicit Codex child model without effort may retain the parent's effort. OrchAtlas warns; choose a level supported by the exact model. OpenCode effort translation supports only `openai/`; other providers can be selected without an override. Provider-specific options are outside this MVP.

Availability and effort capabilities are not resolved from a live catalog. ID syntax and adapter support are checked; account access requires host/provider verification. A documentation example can become unavailable independently of OrchAtlas.

## Adapters

Codex receives builder and optional reviewer TOML files. An explicit planner model is supplied through the command in `START.md`, because child configurations do not change the current root session. The skill checks consistency with explicit planner settings. Respect project trust and session reload requirements of the installed client.

OpenCode receives a primary `orchatlas` agent and its children. The primary embeds the workflow and restricts Task delegation to generated children. The builder cannot delegate through Task. The reviewer has read tools but no edit or shell access; the coordinator supplies the baseline diff and inaccessible evidence. Host overrides and user actions can affect these policies.

The shared skill is installed once under `.agents/skills/orchatlas`, supported by both hosts. Its sections identify each host's roles. Discovery does not guarantee invocation; the documented Codex prompt requests the skill explicitly.

## Maintainer updates

The manifest embeds a recipe snapshot. Updating the CLI/catalog does not change existing projects. `use` selects a new snapshot; `preview` shows its effect before `apply`.

Catalogs are local JSON data. They can include model defaults per host/role, review ownership and correction rounds, but cannot inject arbitrary scripts into the compiler. New projects adopt defaults; `use` preserves existing selections unless `--with-models` is supplied. An omitted host then inherits its host defaults. This schema supports only `unbenchmarked` evidence; benchmark import and verified badges are not implemented.

## Recovery and limits

Transactions detect drift in every managed file and reject linked/reparse-point paths, unowned collisions, invalid receipt paths and concurrent OrchAtlas writers. They do not lock out unrelated programs or form a security boundary against processes with the same filesystem access.

Ordinary write errors and handled interruptions attempt to restore completed writes. Receipts are saved before host files. Process termination, power loss or an I/O failure during rollback can require manual recovery. Retain `.orchatlas/local/`, inspect the latest receipt and files, and reconcile them before removing a stale `write.lock`. A receipt alone does not prove completion; `state.json` records applied history.

For intentionally edited generated files, preserve the edits separately and reconcile the recorded installation before apply/undo. There is no force-overwrite command. Undo preserves `orchatlas.json`, which can still describe a newer desired configuration; `status` then reports pending changes.

Remaining work includes live routed-task evidence, model availability diagnostics, benchmark ingestion, additional platform evidence and a richer model-selection interface. Budget and correction limits are instructions to the agent, not hard runtime enforcement.
