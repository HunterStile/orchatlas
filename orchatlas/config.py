"""Validate the portable manifest and resolve a versioned workflow."""

from __future__ import annotations

import copy
import json
import re
from importlib.resources import files
from pathlib import Path

HOSTS = ("codex", "opencode")
ROLES = ("planner", "builder", "reviewer")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")


class AtlasError(ValueError):
    """An actionable error suitable for CLI output."""


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AtlasError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    try:
        if path.stat().st_size > 2_000_000:
            raise AtlasError(f"File is too large: {path.name}")
        value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AtlasError(f"Cannot read {path.name}: {type(exc).__name__}.") from None
    if not isinstance(value, dict):
        raise AtlasError(f"{path.name} must contain a JSON object.")
    return value


def bundled(name: str) -> dict:
    return json.loads(files("orchatlas").joinpath("data", name).read_text(encoding="utf-8"))


def recipe_catalog(path: Path | None = None) -> dict:
    data = read_json(path) if path else bundled("recipes.json")
    keys(data, {"schema_version", "catalog_version", "default_recipe", "recipes"}, "recipe catalog")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise AtlasError("Recipe catalog requires schema_version 1.")
    identifier(data.get("catalog_version"), "catalog_version")
    if not isinstance(data.get("recipes"), list) or not data["recipes"]:
        raise AtlasError("Recipe catalog requires a nonempty recipes array.")
    seen = set()
    for recipe in data["recipes"]:
        validate_recipe(recipe)
        identity = (recipe["id"], recipe["version"])
        if identity in seen:
            raise AtlasError("Duplicate recipe id/version.")
        seen.add(identity)
    if "default_recipe" in data:
        default = data["default_recipe"]
        if not isinstance(default, str) or default not in {f"{name}@{version}" for name, version in seen}:
            raise AtlasError("default_recipe must name an existing exact id@version in the catalog.")
    return data


def keys(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise AtlasError(f"{label} must be an object.")
    extra = set(value) - allowed
    if extra:
        raise AtlasError(f"Unknown {label} field(s): {', '.join(sorted(extra))}.")


def identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", value):
        raise AtlasError(f"Invalid {label}.")


def validate(config: dict) -> list[str]:
    keys(config, {"schema_version", "catalog_version", "recipe", "hosts"}, "manifest")
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise AtlasError("Manifest requires schema_version 1.")
    identifier(config.get("catalog_version"), "catalog_version")
    # A recipe snapshot travels with the manifest; upgrades never silently change it.
    validate_recipe(config.get("recipe"))
    warnings = validate_hosts(config.get("hosts"))
    warnings.append("Static configuration only: credentials, effective host overrides and live model routing are not verified.")
    return warnings


def validate_hosts(hosts: object) -> list[str]:
    keys(hosts, set(HOSTS), "hosts")
    if not hosts:
        raise AtlasError("Select at least one host.")
    warnings = []
    listed = {(m["host"], m["model"]) for m in bundled("models.json")["models"]}
    for host, roles in hosts.items():
        keys(roles, set(ROLES), host)
        if set(roles) != set(ROLES):
            raise AtlasError(f"{host} requires planner, builder and reviewer settings.")
        for role, settings in roles.items():
            label = f"{host}.{role}"
            keys(settings, {"model", "effort"}, label)
            model = settings.get("model")
            if not isinstance(model, str) or not MODEL_ID.fullmatch(model) or ".." in model or model.endswith("/") or "//" in model:
                raise AtlasError(f"{label}.model must be a model ID, without spaces, substitutions or URLs.")
            if host == "opencode" and model != "inherit" and "/" not in model:
                raise AtlasError(f"{label}.model requires provider/model, for example openai/gpt-5.2.")
            effort = settings.get("effort")
            if effort is not None:
                if effort not in EFFORTS:
                    raise AtlasError(f"{label}.effort must be one of {', '.join(EFFORTS)}.")
                if model == "inherit":
                    raise AtlasError(f"{label}: select an explicit model before setting effort.")
                if host == "opencode" and not model.startswith("openai/"):
                    raise AtlasError(f"{label}: effort translation is supported only for OpenCode's openai/ provider in this MVP.")
                warnings.append(f"{label}: check that {model} supports effort={effort} in your host.")
            if model == "inherit":
                warnings.append(f"{label}: model is inherited, so its exact identity is not pinned.")
            elif (host, model) not in listed:
                warnings.append(f"{label}: custom model {model}; availability and tool support are unverified.")
            if host == "codex" and "/" in model:
                warnings.append(f"{label}: routed model requires a configured provider/router and a spawnable catalog entry for workers.")
            if host == "codex" and model != "inherit" and effort is None and role != "planner":
                warnings.append(f"{label}: no effort pinned; Codex may inherit the parent's effort. Set a supported effort explicitly if needed.")
    return warnings


def validate_recipe(recipe: object) -> None:
    keys(recipe, {"id", "version", "title", "description", "review", "max_fix_rounds", "evidence", "models"}, "recipe")
    for field in ("id", "version"):
        identifier(recipe.get(field), f"recipe.{field}")
    for field in ("title", "description"):
        if not isinstance(recipe.get(field), str) or not recipe[field].strip() or len(recipe[field]) > 500:
            raise AtlasError(f"recipe.{field} must be a short, nonempty string.")
    if recipe.get("review") not in ("coordinator", "independent"):
        raise AtlasError("recipe.review must be coordinator or independent.")
    if type(recipe.get("max_fix_rounds")) is not int or not 0 <= recipe["max_fix_rounds"] <= 5:
        raise AtlasError("recipe.max_fix_rounds must be an integer from 0 to 5.")
    if recipe.get("evidence") != "unbenchmarked":
        raise AtlasError("MVP recipes must declare evidence=unbenchmarked.")
    if "models" in recipe:
        validate_hosts(recipe["models"])


def new_config(recipe_id: str | None = None, hosts: tuple = HOSTS, catalog: dict | None = None) -> dict:
    catalog = catalog or recipe_catalog()
    if recipe_id is None:
        recipe_id = catalog.get("default_recipe", "lean")
    name, separator, version = recipe_id.partition("@")
    matches = [r for r in catalog["recipes"] if r["id"] == name and (not separator or r["version"] == version)]
    if len(matches) != 1:
        raise AtlasError(f"Recipe {recipe_id!r} is missing or ambiguous in the catalog.")
    config = {"schema_version": 1, "catalog_version": catalog["catalog_version"],
              "recipe": copy.deepcopy(matches[0]),
              "hosts": {host: copy.deepcopy(matches[0].get("models", {}).get(host,
                          {role: {"model": "inherit"} for role in ROLES})) for host in hosts}}
    validate(config)
    return config


def set_model(config: dict, selector: str, model: str, effort: str | None = None) -> None:
    parts = selector.split(".")
    if len(parts) != 2 or parts[0] not in config["hosts"] or parts[1] not in ROLES:
        raise AtlasError("Use an enabled host.role, for example codex.builder or opencode.reviewer.")
    settings = {"model": model}
    if effort and effort != "default":
        settings["effort"] = effort
    candidate = copy.deepcopy(config)
    candidate["hosts"][parts[0]][parts[1]] = settings
    validate(candidate)
    config["hosts"][parts[0]][parts[1]] = settings
