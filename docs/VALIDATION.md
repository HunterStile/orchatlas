# Validation evidence

Date: 2026-09-21. Local platform: Windows, Python 3.12.4.

Local result for v0.1.1: **46 tests passed**, no skips. The installed v0.1.1 wheel completed default-team init → apply → status outside the source checkout, generating nine files with no drift or pending changes. The existing local demo was explicitly migrated to `astra-flash@0.1.0` with its model defaults and also has no drift or pending changes.

The main-team tests check the Codex launch model, both hosts' builder/reviewer IDs, route warnings and explicit adoption of defaults without overwriting existing choices automatically. No inference calls are made.

## Offline behavior

The unittest suite covers manifest validation, recipe/model snapshots, both adapters, deterministic hashes, the CLI lifecycle, read-only previews, unowned collisions, drift, obsolete roles, transaction locks, rollback and stacked undo. It uses temporary projects and synthetic configuration; it sends no inference requests.

The link-rejection test simulates a linked directory without requiring Windows symlink privileges. This checks the rejection path, not every operating system's reparse-point behavior.

The generated skill passes the skill-creator `quick_validate.py` check. The PyYAML dependency used by that external validator was installed in a separate validation environment; it is not an OrchAtlas runtime dependency.

## Host configuration loading

These diagnostics were recorded for v0.1.0. They have not been repeated as live task runs for the Astra/DeepSeek main team introduced in v0.1.1.

| Host | Actual local observation | Not established |
| --- | --- | --- |
| Codex CLI 0.155.1 | `codex debug prompt-input` successfully discovers the generated project skill. Generated agent TOML is parsed by Python's TOML parser in tests. | This diagnostic does not prove custom-agent loading: it also accepts an intentionally malformed custom-agent file in a negative control. Actual child selection/model routing remains unverified. |
| OpenCode 1.18.31 | `opencode --pure debug agent` loads primary, builder and reviewer; identifies the builder's `openai/gpt-5.2` model and medium effort; returns the generated Task/read permission rules. | Provider authentication, live inference, task delegation and work quality remain unverified. |

Host checks used synthetic projects and separate config/data locations, with model credentials omitted and no inference requests. Codex still discovered the existing user skill directory through Windows home discovery; that read-only discovery was not presented as proof of complete environment isolation. No personal host configuration was modified.

Both the default/inherited route and explicit model settings are tested at the generated-file level. No claim is made that every documented/custom ID is available in the current account or supports every effort.

## Packaging and automation

A `py3-none-any` wheel was built using the declared build backend. Its installed console command and packaged templates/catalogs are checked outside the source checkout.

GitHub Actions passed all six jobs on Windows, Linux and macOS with Python 3.11 and 3.14: [initial public CI run](https://github.com/HunterStile/orchatlas/actions/runs/35642424500), commit `2d9bb95`. Each job runs the test suite, installs the package and checks the console entry point. This is offline compatibility evidence, not model execution evidence.

## Remaining acceptance work

- Run a real implementation and review with recorded host/provider identity on each host.
- Measure identical tasks across model teams, including failures and coordination cost.
- Verify additional provider-specific effort mappings and account availability.
- Expand filesystem coverage for real symlinks, Windows reparse points and process interruption.

The CLI's `static-valid` result and lock file deliberately keep `runtime_verified: false`. Neither a passing suite nor a discovered agent changes that claim.
