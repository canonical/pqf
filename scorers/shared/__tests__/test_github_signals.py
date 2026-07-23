import responses

from scorers.shared.github_signals import (
    default_branch_check_runs,
    repo_file_exists,
    repo_topics,
    search_code_count,
    workflow_files,
)


@responses.activate
def test_repo_file_exists_true():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/contents/README.md",
        json={"name": "README.md"},
        status=200,
    )
    assert repo_file_exists("canonical/example", "README.md", "gh-token") is True


@responses.activate
def test_repo_topics_reads_topic_names():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/topics",
        json={"names": ["squad-data", "platform-engineering"]},
        status=200,
    )
    assert repo_topics("canonical/example", "gh-token") == ["squad-data", "platform-engineering"]


@responses.activate
def test_search_code_count_returns_total_count():
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        json={"total_count": 3},
        status=200,
    )
    assert search_code_count("repo:canonical/example import jubilant", "gh-token") == 3


@responses.activate
def test_search_code_count_retries_anonymously_on_auth_error():
    # First attempt with token returns 403 (visibility/auth related),
    # second (anonymous) attempt succeeds with the count.
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        status=403,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        json={"total_count": 2},
        status=200,
    )
    assert search_code_count("repo:canonical/example import jubilant", "gh-token") == 2


@responses.activate
def test_workflow_files_returns_name_and_text_pairs():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/contents/.github/workflows",
        json=[
            {
                "type": "file",
                "name": "ci.yaml",
                "url": "https://api.github.com/repos/canonical/example/contents/.github/workflows/ci.yaml",
            }
        ],
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/contents/.github/workflows/ci.yaml",
        json={"content": "bmFtZTogQ0kK", "encoding": "base64"},
        status=200,
    )
    assert workflow_files("canonical/example", "gh-token") == [("ci.yaml", "name: CI\n")]


@responses.activate
def test_github_token_is_sent_in_authorization_header():
    seen = []

    def callback(request):
        # record whether the Authorization header contains the expected token scheme
        auth = request.headers.get("Authorization")
        if auth == "token gh-token":
            seen.append(True)
        return (200, {}, '{"name": "README.md"}')

    responses.add_callback(
        responses.GET,
        "https://api.github.com/repos/canonical/example/contents/README.md",
        callback=callback,
    )

    assert repo_file_exists("canonical/example", "README.md", "gh-token") is True
    assert seen == [True]


@responses.activate
def test_default_branch_check_runs_returns_check_runs():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example",
        json={"default_branch": "main"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/branches/main",
        json={"commit": {"sha": "abc123"}},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/commits/abc123/check-runs",
        match=[responses.matchers.query_param_matcher({"per_page": "100", "page": "1"})],
        json={"check_runs": [{"name": "ci", "conclusion": "success"}]},
        status=200,
    )

    assert default_branch_check_runs("canonical/example", "gh-token") == [
        {"name": "ci", "conclusion": "success"}
    ]


@responses.activate
def test_default_branch_check_runs_paginates_all_pages():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example",
        json={"default_branch": "main"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/branches/main",
        json={"commit": {"sha": "abc123"}},
        status=200,
    )
    page1_runs = [{"name": f"ci-{i}", "conclusion": "success"} for i in range(100)]
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/commits/abc123/check-runs",
        match=[responses.matchers.query_param_matcher({"per_page": "100", "page": "1"})],
        json={"check_runs": page1_runs},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/commits/abc123/check-runs",
        match=[responses.matchers.query_param_matcher({"per_page": "100", "page": "2"})],
        json={"check_runs": [{"name": "docs", "conclusion": "success"}]},
        status=200,
    )

    runs = default_branch_check_runs("canonical/example", "gh-token")
    assert len(runs) == 101
    assert runs[0]["name"] == "ci-0"
    assert runs[-1]["name"] == "docs"
