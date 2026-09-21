# Contributing

Use Python 3.11+, install the checkout with `python -m pip install -e .`, and run `python -m unittest discover -s tests -v`. The terminal uses `prompt-toolkit` and `rich`; orchestration and protocol handling use the standard library. Keep host-specific compilation in `render.py`, manifest validation in `config.py`, and filesystem transactions in `storage.py`.

`interactive.py` owns terminal interaction and slash-command dispatch. `session.py` owns conversation persistence and bounded context assembled from saved runs. Test the dispatch interface through the actual runtime with local protocol fixtures; also exercise real prompt input for keyboard behavior. Never put credentials in prompt history.

Version bumps and publication require the maintainer's instruction. `runtime.py` owns orchestration, `clients.py` owns native subprocess/protocol handling, and `runstore.py` owns saved runs and working-tree evidence. Test through these interfaces using the protocol fixtures; tests must not invoke a paid model or read personal credentials. The existing `hosts` manifest supports both paths: combined execution uses Codex planner/reviewer plus OpenCode builder, while exports use each host's full role set.

## Maintain recipes

Recipes live in `orchatlas/data/recipes.json`. Give each change to an existing recipe a new version and increment `catalog_version`. Keep historical versions if projects need to select them again. IDs with multiple versions require explicit `id@version` selection.

Set the catalog's `default_recipe` to an existing exact `id@version` to choose the main team for new projects. It is currently `astra-flash@0.1.0`: Astra orchestrates and reviews, DeepSeek V4.1 Flash implements. Existing projects adopt changed models only with `use --with-models` followed by `apply`.

That catalog describes the historical configuration exports. The combined runtime defaults to `openrouter/deepseek/deepseek-v4.1-flash` without changing published recipe snapshots. `/model` saves runtime choices in the project manifest for new tasks and needs no `apply`. Authentication checks reuse the effective OpenRouter credential from OpenCode only in memory; never print or persist provider responses containing keys.

The current schema supports `review: coordinator|independent` and `max_fix_rounds` from 0 to 5. Keep `evidence: unbenchmarked`; provenance checks for verification badges are not implemented. The bundled recipes are workflow starting points, not comparative model recommendations.

A recipe may include a `models` object containing complete planner/builder/reviewer settings for each included host. See [the example catalog](examples/recipes.json). New projects adopt these defaults; existing projects retain their choices unless the user passes `use --with-models`. A host omitted from defaults uses inheritance when defaults are adopted.

Model examples live in `orchatlas/data/models.json`. Include a primary source for every example and distinguish its documented format from availability in an account. New provider-specific options need an explicit translation and meaningful tests.

## Evidence

Report separately: offline checks, client/version configuration loading, and actual task runs. Runtime evidence should name the exact model/provider, host version, recipe snapshot, task baseline, acceptance checks, outcome and usage source. Remove secrets and private prompts before publishing evidence.

The portable link-rejection test simulates a linked path, avoiding Windows symlink privilege requirements. Real symlink checks add platform evidence; they do not replace that baseline.

## Scope

The CLI owns combined orchestration and optional configuration exports. Authentication and model execution remain with the official clients; orchestration, handoffs and saved run progress belong to OrchAtlas. Keep generated instructions concise and tied to observable completion criteria. Explain the user-visible benefit of new dependencies or host configuration mutations.
