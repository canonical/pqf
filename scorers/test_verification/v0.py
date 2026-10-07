"""Pure V0 testing measurements over a pinned repository evidence snapshot."""

import ast
import itertools
import posixpath
import re
import shlex
from typing import Any

import yaml

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured, not_applicable
from engine.models import EvaluationUnit, ProductType
from scorers.test_verification.terraform import terraform_outcome

CHARM_METRICS = (
    "uses_ops_testing",
    "uses_jubilant",
    "uses_charm_ci",
    "uses_gh_runners_unit_testing",
    "uses_tf_v1_provider",
    "supports_canonical_k8s",
    "supports_juju_4",
    "supports_juju_lts",
)
_MATRIX = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")
_HOSTED = re.compile(r"^(ubuntu|windows|macos)-(latest|\d+(?:\.\d+)*(?:-[a-z0-9-]+)?)$")
_INTEGRATION = re.compile(
    r"^canonical/charm-ci/\.github/workflows/integration[-_]tests?\.(yml|yaml)@[^@\s]+$"
)
_UNIT = re.compile(r"^canonical/operator-workflows/\.github/workflows/test\.(yml|yaml)@[^@\s]+$")
_K8S_EXTENSIONS = {
    "django-framework",
    "fastapi-framework",
    "flask-framework",
    "go-framework",
    "expressjs-framework",
    "spring-boot-framework",
}


def normalize(path: str) -> str:
    return posixpath.normpath(path).removeprefix("./").rstrip("/") if path else "."


def scoped(path: str, scope: str) -> bool:
    return scope == "." or path == scope or path.startswith(scope + "/")


def _yaml(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a YAML mapping")
    return data


def _python_outcome(files: dict[str, str], *, jubilant: bool) -> MetricOutcome:
    unknown = False
    ops_import = False
    for path, text in files.items():
        parts = path.split("/")
        if not path.endswith(".py") or "tests" not in parts:
            continue
        test_scope = "integration" if jubilant else "unit"
        if not any(parts[i : i + 2] == ["tests", test_scope] for i in range(len(parts) - 1)):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            unknown = True
            continue
        aliases = {"ops": "ops"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if jubilant and alias.name.split(".")[0] == "jubilant":
                        return measured(True)
                    if alias.name == "ops.testing" or alias.name.startswith("ops.testing."):
                        ops_import = True
                    aliases[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
            elif isinstance(node, ast.ImportFrom) and not node.level:
                module = node.module or ""
                for alias in node.names:
                    if jubilant and module.split(".")[0] == "jubilant":
                        return measured(True)
                    qualified = f"{module}.{alias.name}"
                    if (
                        module == "ops.testing"
                        or module.startswith("ops.testing.")
                        or (module == "ops" and alias.name == "testing")
                    ):
                        ops_import = True
                    aliases[alias.asname or alias.name] = qualified
                    if not jubilant and qualified in {"ops.testing.Harness", "ops.testing.*"}:
                        return measured(False)
        if not jubilant:
            for node in ast.walk(tree):
                parts = []
                while isinstance(node, ast.Attribute):
                    parts.insert(0, node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    qualified = ".".join([aliases.get(node.id, node.id), *parts])
                    if qualified == "ops.testing.Harness":
                        return measured(False)
    if unknown:
        return insufficient_data("Cannot parse scoped Python tests.")
    return measured(ops_import if not jubilant else False)


def _expand(job: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = job.get("strategy", {}).get("matrix", {})
    if not isinstance(matrix, dict):
        raise ValueError("Dynamic workflow matrix")
    axes = {key: value for key, value in matrix.items() if key not in {"include", "exclude"}}
    if any(not isinstance(value, list) for value in axes.values()):
        raise ValueError("Dynamic workflow matrix")
    combinations = [
        dict(zip(axes, values, strict=True)) for values in itertools.product(*axes.values())
    ]
    exclusions = matrix.get("exclude", [])
    if not isinstance(exclusions, list) or not all(isinstance(v, dict) for v in exclusions):
        raise ValueError("Invalid matrix exclusions")
    combinations = [
        item
        for item in combinations
        if not any(all(item.get(k) == v for k, v in rule.items()) for rule in exclusions)
    ]
    includes = matrix.get("include", [])
    if not isinstance(includes, list) or not all(isinstance(v, dict) for v in includes):
        raise ValueError("Invalid matrix includes")
    for item in includes:
        matched = False
        for combination in combinations:
            if all(k not in axes or combination.get(k) == v for k, v in item.items()):
                combination.update(item)
                matched = True
        if not matched:
            combinations.append(item)

    def replace(value: Any, variables: dict[str, Any]) -> Any:
        if isinstance(value, str):
            match = _MATRIX.fullmatch(value)
            if match:
                return variables.get(match.group(1), value)
            return _MATRIX.sub(lambda m: str(variables.get(m.group(1), m.group())), value)
        if isinstance(value, list):
            return [replace(v, variables) for v in value]
        if isinstance(value, dict):
            return {k: replace(v, variables) for k, v in value.items()}
        return value

    return [replace(job, item) for item in combinations]


def _directory(job: dict[str, Any], workflow: dict[str, Any]) -> str:
    inputs = job.get("with", {})
    keys = (
        ("working-directory",)
        if _UNIT.fullmatch(str(job.get("uses", "")))
        else ("working-directory", "charm-directory")
    )
    directories = [inputs[key] for key in keys if key in inputs]
    if not directories:
        directories = [
            job.get("defaults", workflow.get("defaults", {}))
            .get("run", {})
            .get("working-directory", ".")
        ]
    if any(not isinstance(p, str) or "${{" in p for p in directories):
        raise ValueError("Dynamic component directory")
    normalized = {normalize(p) for p in directories}
    if len(normalized) != 1:
        raise ValueError("Conflicting component directories")
    directory = normalized.pop()
    if directory.startswith(("../", "/")) or directory == "..":
        raise ValueError("Directory escapes repository")
    return directory


def _is_unit(job: dict[str, Any], scope: str, directory: str) -> bool:
    if _UNIT.fullmatch(str(job.get("uses", ""))):
        return directory == scope
    for step in job.get("steps", []):
        if not isinstance(step, dict) or not isinstance(step.get("run"), str):
            continue
        step_directory = normalize(step.get("working-directory", directory))
        for line in step["run"].splitlines():
            try:
                tokens = shlex.split(line)
            except ValueError:
                continue
            if not tokens:
                continue
            if tokens[:2] == ["uv", "run"]:
                tokens = tokens[2:]
            if tokens[:2] in (["python", "-m"], ["python3", "-m"]):
                tokens = tokens[2:]
            if not tokens:
                continue
            command = tokens[0]
            if command in {"tox", "tox-uv"} and step_directory == scope:
                for index, token in enumerate(tokens):
                    environments = (
                        tokens[index + 1]
                        if token == "-e" and index + 1 < len(tokens)
                        else token.removeprefix("-e")
                        if token.startswith("-e")
                        else ""
                    )
                    if any(env in {"unit", "unit-tests"} for env in environments.split(",")):
                        return True
            if command == "pytest":
                for token in tokens[1:]:
                    if token.startswith("-"):
                        continue
                    test_path = normalize(posixpath.join(step_directory, token))
                    if test_path == normalize(posixpath.join(scope, "tests/unit")) or (
                        test_path.startswith(normalize(posixpath.join(scope, "tests/unit")) + "/")
                    ):
                        return True
    return False


def _runner(job: dict[str, Any]) -> MetricOutcome:
    inputs = job.get("with", {})
    if _UNIT.fullmatch(str(job.get("uses", ""))):
        self_hosted = inputs.get("self-hosted-runner", False)
        if self_hosted is True or self_hosted == "true":
            return measured(False)
        if self_hosted not in (False, "false"):
            return insufficient_data("Dynamic self-hosted-runner input.")
        runner = inputs.get("runs-on-base", "ubuntu-latest")
    else:
        runner = job.get("runs-on")
    if isinstance(runner, dict):
        if "group" in runner:
            return insufficient_data("Runner group is not identifiable as GitHub-hosted.")
        runner = runner.get("labels")
    labels = runner if isinstance(runner, list) else [runner]
    if any(isinstance(label, str) and label.startswith("self-hosted") for label in labels):
        return measured(False)
    if labels and all(isinstance(label, str) and _HOSTED.fullmatch(label) for label in labels):
        return measured(True)
    return insufficient_data("Unit-test runner is dynamic or not a known GitHub-hosted label.")


def _all(outcomes: list[MetricOutcome]) -> MetricOutcome:
    if any(item.value is False for item in outcomes):
        return measured(False)
    unknown = next((item for item in outcomes if item.state.value == "insufficient_data"), None)
    return unknown or measured(bool(outcomes))


def _any(outcomes: list[MetricOutcome]) -> MetricOutcome:
    if any(item.value is True for item in outcomes):
        return measured(True)
    unknown = next((item for item in outcomes if item.state.value == "insufficient_data"), None)
    return unknown or measured(False)


def _kubernetes(files: dict[str, str], scope: str) -> MetricOutcome:
    def assumes_k8s(value: object) -> bool:
        if isinstance(value, list):
            return any(assumes_k8s(item) for item in value)
        if isinstance(value, dict):
            return any(
                assumes_k8s(item) for key, item in value.items() if key in {"any-of", "all-of"}
            )
        return value == "k8s-api"

    present = False
    for name in ("charmcraft.yaml", "metadata.yaml"):
        path = posixpath.join(scope, name).removeprefix("./")
        if path not in files:
            continue
        present = True
        try:
            data = _yaml(files[path])
            if data.get("containers") or assumes_k8s(data.get("assumes", [])):
                return measured(True)
            if isinstance(data.get("extensions"), list) and any(
                isinstance(extension, str) and extension in _K8S_EXTENSIONS
                for extension in data["extensions"]
            ):
                return measured(True)
            if "kubernetes" in data.get("series", []):
                return measured(True)
        except (yaml.YAMLError, ValueError, TypeError):
            return insufficient_data("Cannot interpret scoped charm metadata.")
    return measured(False) if present else insufficient_data("Scoped charm metadata is absent.")


def concierge_path(path: object) -> str:
    """Interpret a literal path or the documented Spread default-path expression."""
    if not isinstance(path, str):
        raise ValueError("Concierge configuration path is not a string")
    default = re.fullmatch(r'\$\(HOST:\s*echo\s+"\$\{CONCIERGE:-([A-Za-z0-9_./-]+)\}"\s*\)', path)
    if default:
        return default.group(1)
    if not path.strip() or "${{" in path or "$" in path:
        raise ValueError("Dynamic Concierge configuration path")
    return path


def _resolve(directory: str, path: object) -> str:
    if not isinstance(path, str) or not path.strip() or "${{" in path or "$(" in path:
        raise ValueError("Dynamic Concierge configuration path")
    resolved = normalize(posixpath.join(directory, path))
    if resolved.startswith(("../", "/")) or resolved == "..":
        raise ValueError("Concierge path escapes repository")
    return resolved


def _configurations(
    job: dict[str, Any], directory: str, scope: str, files: dict[str, str]
) -> tuple[list[dict[str, Any]], bool, bool]:
    inputs = job.get("with", {})
    configurations = []
    unknown = False
    paths = []
    applies = directory == scope
    spread_path = posixpath.join(directory, "spread.yaml").removeprefix("./")
    if spread_path in files:
        spread = _yaml(files[spread_path])
        suites = spread.get("integration-suites", {})
        if not isinstance(suites, dict):
            raise ValueError("Invalid spread integration suites")
        for path, suite in suites.items():
            if not isinstance(suite, dict):
                raise ValueError("Invalid spread suite")
            working = _resolve(directory, suite.get("working-dir", "."))
            if working != scope or not scoped(
                _resolve(directory, path), normalize(posixpath.join(scope, "tests/integration"))
            ):
                continue
            backends = suite.get("backends", [])
            known = spread.get("backends", {})
            if not isinstance(backends, list) or not isinstance(known, dict):
                raise ValueError("Invalid spread backends")
            if not any(
                backend == "integration-test"
                or isinstance(known.get(backend), dict)
                and known[backend].get("type") == "integration-test"
                for backend in backends
            ):
                continue
            applies = True
            if inputs.get("spread-jobs-include"):
                # Arbitrary fnmatch selection can omit a suite/system/variant.
                unknown = True
                continue
            environment = {
                **spread.get("environment", {}),
                **suite.get("environment", {}),
            }
            suite_paths = [
                value
                for key, value in environment.items()
                if key == "CONCIERGE" or key.startswith("CONCIERGE/")
            ]
            if not suite_paths:
                suite_paths = ["concierge.yaml"]
            for value in suite_paths:
                try:
                    paths.append(_resolve(directory, concierge_path(value)))
                except ValueError:
                    unknown = True
    for path in paths:
        if path not in files:
            continue
        try:
            configurations.append(_yaml(files[path]))
        except (yaml.YAMLError, ValueError):
            unknown = True
    return configurations, unknown, applies


def evaluate_files(
    unit: EvaluationUnit,
    files: dict[str, str],
    *,
    juju4_track: str = "4/stable",
    juju_lts_track: str = "3.6/stable",
) -> dict[str, MetricOutcome]:
    if unit.product_type != ProductType.CHARM:
        return {key: not_applicable("This is not a charm.") for key in CHARM_METRICS}
    scope = normalize(unit.subpath or ".")
    other_charms = [
        normalize(posixpath.dirname(path))
        for path in files
        if path.rsplit("/", 1)[-1] == "charmcraft.yaml"
        and normalize(posixpath.dirname(path)) != scope
        and scoped(path, scope)
    ]
    component = {
        path: text
        for path, text in files.items()
        if scoped(path, scope) and not any(scoped(path, other) for other in other_charms)
    }
    result = {
        "uses_ops_testing": _python_outcome(component, jubilant=False),
        "uses_jubilant": _python_outcome(component, jubilant=True),
        "uses_tf_v1_provider": terraform_outcome(component),
    }
    unit_runners = []
    charm_ci = []
    configurations = []
    configuration_unknown = False
    for path, text in files.items():
        if not path.startswith(".github/workflows/") or not path.endswith((".yaml", ".yml")):
            continue
        try:
            workflow = _yaml(text)
            jobs = workflow.get("jobs", {})
            if not isinstance(jobs, dict):
                raise ValueError("Invalid workflow jobs")
            for job in jobs.values():
                if not isinstance(job, dict):
                    raise ValueError("Invalid workflow job")
                if job.get("if") is False or job.get("if") in {"false", "${{ false }}"}:
                    continue
                try:
                    expanded = _expand(job)
                    for item in expanded:
                        directory = _directory(item, workflow)
                        if _is_unit(item, scope, directory):
                            unit_runners.append(_runner(item))
                        if _INTEGRATION.fullmatch(str(item.get("uses", ""))):
                            # Root workflows may explicitly enumerate component suites.
                            if directory != scope and directory != ".":
                                continue
                            if directory == scope:
                                charm_ci.append(measured(True))
                            try:
                                configs, unknown, applies = _configurations(
                                    item, directory, scope, files
                                )
                            except (yaml.YAMLError, ValueError, TypeError, AttributeError):
                                configuration_unknown = True
                                if directory != scope:
                                    charm_ci.append(
                                        insufficient_data(
                                            "Cannot resolve charm-ci integration suites."
                                        )
                                    )
                                continue
                            if applies:
                                charm_ci.append(measured(True))
                                configurations.extend(configs)
                                configuration_unknown |= unknown
                except (ValueError, TypeError, AttributeError):
                    if _INTEGRATION.fullmatch(str(job.get("uses", ""))):
                        charm_ci.append(insufficient_data("Cannot resolve charm-ci job scope."))
                        configuration_unknown = True
                    elif _UNIT.fullmatch(str(job.get("uses", ""))) or job.get("steps"):
                        unit_runners.append(
                            insufficient_data("Cannot resolve unit-test job scope.")
                        )
        except (yaml.YAMLError, ValueError, TypeError, AttributeError):
            charm_ci.append(insufficient_data(f"Cannot parse workflow {path}."))
            unit_runners.append(insufficient_data(f"Cannot parse workflow {path}."))
            configuration_unknown = True
    result["uses_charm_ci"] = _any(charm_ci)
    result["uses_gh_runners_unit_testing"] = _all(unit_runners)
    for key, track in (("supports_juju_4", juju4_track), ("supports_juju_lts", juju_lts_track)):
        outcomes = []
        for config in configurations:
            juju = config.get("juju", {})
            if not isinstance(juju, dict):
                outcomes.append(insufficient_data("Cannot interpret Concierge Juju configuration."))
            else:
                channel = juju.get("channel", "")
                outcomes.append(
                    insufficient_data("Dynamic Juju channel.")
                    if not isinstance(channel, str) or "${{" in channel
                    else measured(channel == track)
                )
        if configuration_unknown:
            outcomes.append(insufficient_data("Cannot resolve linked charm-ci configuration."))
        result[key] = _any(outcomes)
    kubernetes = _kubernetes(files, scope)
    if kubernetes.value is False:
        result["supports_canonical_k8s"] = not_applicable("This is a machine charm.")
    elif kubernetes.value is None:
        result["supports_canonical_k8s"] = kubernetes
    else:
        outcomes = []
        for config in configurations:
            providers = config.get("providers", {})
            if not isinstance(providers, dict):
                outcomes.append(insufficient_data("Cannot interpret Concierge providers."))
                continue
            k8s = providers.get("k8s")
            if "k8s" not in providers:
                outcomes.append(measured(False))
            elif not isinstance(k8s, dict):
                outcomes.append(insufficient_data("Cannot interpret Concierge k8s provider."))
            else:
                enabled = k8s.get("enable", True)
                bootstrap = k8s.get("bootstrap", True)
                if not isinstance(enabled, bool) or not isinstance(bootstrap, bool):
                    outcomes.append(insufficient_data("Dynamic Concierge k8s provider."))
                else:
                    outcomes.append(measured(enabled and bootstrap))
        if configuration_unknown:
            outcomes.append(insufficient_data("Cannot resolve linked charm-ci configuration."))
        result["supports_canonical_k8s"] = _any(outcomes)
    return result


def evaluate_checks(
    checks: list[dict[str, Any]],
    *,
    statuses: list[dict[str, Any]] | None = None,
    required: set[str] | None = None,
) -> MetricOutcome:
    def rank(item: dict[str, Any]) -> tuple[str, int]:
        return (
            str(item.get("started_at") or item.get("created_at") or ""),
            int(item.get("id", 0)),
        )

    latest: dict[tuple[object, str], dict[str, Any]] = {}
    for check in checks:
        key = (check.get("app", {}).get("id"), check.get("name", ""))
        if not key[1]:
            return insufficient_data("Check identity is absent.")
        if key not in latest or rank(check) > rank(latest[key]):
            latest[key] = check
    latest_statuses: dict[str, dict[str, Any]] = {}
    for status in statuses or []:
        context = status.get("context", "")
        if not context:
            return insufficient_data("Commit status identity is absent.")
        if context not in latest_statuses or (
            str(status.get("created_at") or ""),
            int(status.get("id", 0)),
        ) > (
            str(latest_statuses[context].get("created_at") or ""),
            int(latest_statuses[context].get("id", 0)),
        ):
            latest_statuses[context] = status
    outcomes = []
    for check in latest.values():
        conclusion = check.get("conclusion")
        if conclusion in {
            "failure",
            "cancelled",
            "timed_out",
            "action_required",
            "startup_failure",
        }:
            outcomes.append(measured(False))
        elif check.get("status") == "completed" and conclusion == "success":
            outcomes.append(measured(True))
        else:
            outcomes.append(
                insufficient_data("A relevant check is pending, skipped or inconclusive.")
            )
    for status in latest_statuses.values():
        state = status.get("state")
        outcomes.append(
            measured(state == "success")
            if state in {"success", "failure", "error"}
            else insufficient_data("A relevant commit status is pending or inconclusive.")
        )
    names = {key[1] for key in latest} | set(latest_statuses)
    if required and not required.issubset(names):
        outcomes.append(insufficient_data("Required jobs are missing from the branch tip checks."))
    return (
        _all(outcomes) if outcomes else insufficient_data("No branch-tip CI jobs were identified.")
    )
