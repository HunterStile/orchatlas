# Contributing

Use Python 3.11+ and run `python -m unittest discover -s tests -v`. Runtime code depends only on the standard library. Keep host-specific compilation in `render.py`, manifest validation in `config.py`, and filesystem transactions in `storage.py`.

## Maintain recipes

Recipes live in `orchatlas/data/recipes.json`. Give each change to an existing recipe a new version and increment `catalog_version`. Keep historical versions if projects need to select them again. IDs with multiple versions require explicit `id@version` selection.

Set the catalog's `default_recipe` to an existing exact `id@version` to choose the main team for new projects. It is currently `astra-flash@0.1.0`: Astra orchestrates and reviews, DeepSeek V4.1 Flash implements. Existing projects adopt changed models only with `use --with-models` followed by `apply`.

The current schema supports `review: coordinator|independent` and `max_fix_rounds` from 0 to 5. Keep `evidence: unbenchmarked`; provenance checks for verification badges are not implemented. The bundled recipes are workflow starting points, not comparative model recommendations.

A recipe may include a `models` object containing complete planner/builder/reviewer settings for each included host. See [the example catalog](examples/recipes.json). New projects adopt these defaults; existing projects retain their choices unless the user passes `use --with-models`. A host omitted from defaults uses inheritance when defaults are adopted.

Model examples live in `orchatlas/data/models.json`. Include a primary source for every example and distinguish its documented format from availability in an account. New provider-specific options need an explicit translation and meaningful tests.

## Evidence

Report separately: offline checks, client/version configuration loading, and actual task runs. Runtime evidence should name the exact model/provider, host version, recipe snapshot, task baseline, acceptance checks, outcome and usage source. Remove secrets and private prompts before publishing evidence.

The portable link-rejection test simulates a linked path, avoiding Windows symlink privilege requirements. Real symlink checks add platform evidence; they do not replace that baseline.

## Scope

The CLI handles configuration and installation. Authentication, provider routing and task execution belong to the host or an explicitly integrated component. Keep generated instructions concise and tied to observable completion criteria. Explain the user-visible benefit of new dependencies or host configuration mutations.
