# Validation evidence

## v0.2.0 combined runtime and interactive terminal

On 2026-09-22, **all 86 tests passed in the full release suite** on Windows / Python 3.12. Protocol fixtures use real subprocess JSON messaging and authenticated loopback HTTP; the upstream key-validation tests mock only the external OpenRouter endpoint. No test-suite call uses personal credentials or paid inference.

The checks cover saved conversations and bounded follow-up context, multiline keyboard input, Ctrl+C returning to the prompt, command completion, exact model selection, configuration persistence, both client protocols, independent review, correction limits, malformed results, permissions, model substitution, cancellation/resume, timeout, concurrent edits, secret redaction and process cleanup.

### Live local evidence

- Codex 0.155.1 detects the existing ChatGPT login and `gpt-6-astra`; returned threads confirm OpenAI routing and a read-only sandbox.
- OpenCode 1.18.31 detects the already configured **OpenRouter** connection and the exact `deepseek/deepseek-v4.1-flash` model. Its effective key was verified at OpenRouter's authenticated `/api/v1/key` endpoint, without inference or credential persistence in project files.
- The installed `orchatlas.exe` opened the interactive shell in a scratch project. Astra planned a one-file task, DeepSeek V4.1 Flash through OpenRouter wrote `hello.txt`, and Astra independently reviewed the saved file. A strict review-result check initially rejected a contradictory response that combined acceptance with nonblocking findings. After clarifying that contract, the saved review was resumed and the run completed with checks and no blocking findings. The final file was independently asserted to contain exactly `OrchAtlas OK` followed by LF.
- The initial direct-DeepSeek route returned HTTP 401 because it was the wrong route for the user's OpenRouter credential. The default combined route, demo manifest and the user's interrupted planning run were corrected to OpenRouter. No new login was required; the existing native credential was reused.
- The Windows installer registered the editable source checkout and `orchatlas.exe` in the user's Python scripts directory and user PATH. The v0.2.0 wheel was separately installed and its version, interactive shell and console entry point checked outside the source checkout.

This live smoke task verifies authentication, routing, actual file saving, review and continuation on a small example. It is not a benchmark or a claim of parity with every Codex/OpenCode feature. The v0.2.0 release includes a wheel, source archive and SHA-256 checksums; archive contents were checked to exclude demo projects, credentials and local session state. Current automation is available in the [CI workflow](https://github.com/HunterStile/orchatlas/actions/workflows/tests.yml). The historical CI run linked below belongs to the earlier configuration exporter.

## Published exporter evidence

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

- Expand live combined-runtime validation to Linux and macOS and to larger implementation tasks.
- Measure identical tasks across model teams, including failures and coordination cost.
- Verify additional provider-specific effort mappings and account availability.
- Expand filesystem coverage for real symlinks, Windows reparse points and process interruption.

The configuration exporter's `static-valid` result and lock file deliberately keep `runtime_verified: false`. Neither a passing suite nor a discovered agent changes that claim. Combined-runtime reports separately record the outcome of each actual run.
