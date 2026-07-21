import base64
import json
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _make_github_session(github_token: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    if github_token:
        session.headers["Authorization"] = f"Bearer {github_token}"
    return session


def _github_get(url: str, github_token: str) -> requests.Response:
    resp = _make_github_session(github_token).get(url, timeout=15)
    if github_token and resp.status_code in {401, 403, 404}:
        # PR GITHUB_TOKENs can lack cross-repo access even for public repos.
        resp = _make_github_session().get(url, timeout=15)
    return resp


def _check_file_exists(owner_repo: str, filename: str, github_token: str) -> bool:
    """Return True if the file exists in the repo's default branch root."""
    url = f"{_GITHUB_API}/repos/{owner_repo}/contents/{filename}"
    resp = _github_get(url, github_token)
    return resp.status_code == 200


def _check_url_alive(url: str) -> bool:
    """Return True if the URL returns a 2xx response."""
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True)
        return resp.ok
    except requests.RequestException:
        return False


def _fetch_readme(owner_repo: str, github_token: str) -> str:
    """Fetch README.md content. Returns empty string if not found."""
    url = f"{_GITHUB_API}/repos/{owner_repo}/readme"
    resp = _github_get(url, github_token)
    if not resp.ok:
        return ""
    data = resp.json()
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content


def _make_openrouter_client(api_key: str) -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _evaluate_docs(
    readme_content: str,
    prompt_path: Path,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
) -> dict[str, Any]:
    """Call OpenRouter using the given prompt file. Returns parsed JSON dict."""
    prompt = prompt_path.read_text()
    client = _make_openrouter_client(openrouter_api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": readme_content or "(no documentation found)"},
        ],
    )
    raw = response.choices[0].message.content or ""
    # Strip markdown code fences if the model wrapped the JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]  # drop opening fence line
        raw = raw.rsplit("```", 1)[0]  # drop closing fence
    return json.loads(raw.strip())


def compute_metrics(
    unit: EvaluationUnit,
    github_token: str,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
) -> dict[str, Any]:
    """
    Evaluate documentation quality for the evaluation unit's repo.

    File checks (has_readme, has_contributing, has_security) use the GitHub API.
    links_passing checks that the documentation_url returns a 200 response.
    diataxis_coverage and style_linter_passing are evaluated by an OpenRouter model.
    """
    primary = unit.repo or None
    has_readme = _check_file_exists(primary, "README.md", github_token) if primary else False
    has_contributing = (
        _check_file_exists(primary, "CONTRIBUTING.md", github_token) if primary else False
    )
    has_security = _check_file_exists(primary, "SECURITY.md", github_token) if primary else False

    doc_url = unit.documentation_url.strip()
    links_passing = _check_url_alive(doc_url) if doc_url else False

    if openrouter_api_key:
        readme_content = _fetch_readme(primary, github_token) if primary else ""
        diataxis_result = _evaluate_docs(
            readme_content,
            _PROMPTS_DIR / "diataxis_check.md",
            openrouter_api_key,
            model,
        )
        style_result = _evaluate_docs(
            readme_content,
            _PROMPTS_DIR / "style_review.md",
            openrouter_api_key,
            model,
        )
        diataxis_coverage = int(diataxis_result.get("diataxis_coverage", 0))
        style_linter_passing = bool(style_result.get("style_linter_passing", False))
    else:
        diataxis_coverage = 0
        style_linter_passing = False

    return {
        "has_readme": has_readme,
        "has_contributing": has_contributing,
        "has_security": has_security,
        "diataxis_coverage": diataxis_coverage,
        "style_linter_passing": style_linter_passing,
        "links_passing": links_passing,
    }
