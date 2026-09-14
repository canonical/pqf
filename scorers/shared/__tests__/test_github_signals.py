import pytest
import requests
import responses

from scorers.shared import github_signals
from scorers.shared.github_signals import (
    GitHubAcquisitionError,
    build_github_session,
    default_branch_check_runs,
    repo_file_exists,
    repo_file_text,
    repo_releases,
    repo_topics,
    search_code_count,
    workflow_files,
)


@responses.activate
def test_session_get_retries_rate_limited_request_anonymously():
    url = "https://api.github.com/repos/canonical/example/issues"
    responses.add(
        responses.GET,
        url,
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={"X-RateLimit-Remaining": "0"},
    )
    responses.add(responses.GET, url, json=[], status=200)

    response = github_signals.github_session_get(build_github_session("gh-token"), url)

    assert response.ok
    assert len(responses.calls) == 2
    assert responses.calls[0].request.headers["Authorization"] == "token gh-token"
    assert "Authorization" not in responses.calls[1].request.headers


@responses.activate
def test_session_get_retries_authenticated_unauthorized_request_anonymously():
    url = "https://api.github.com/repos/canonical/example/topics"
    responses.add(
        responses.GET,
        url,
        json={"message": "Bad credentials"},
        status=401,
    )
    responses.add(responses.GET, url, json={"names": ["squad-example"]}, status=200)

    response = github_signals.github_session_get(build_github_session("gh-token"), url)

    assert response.ok
    assert len(responses.calls) == 2
    assert responses.calls[0].request.headers["Authorization"] == "token gh-token"
    assert "Authorization" not in responses.calls[1].request.headers


@responses.activate
def test_session_get_does_not_retry_permission_failure():
    url = "https://api.github.com/repos/canonical/example/traffic/views"
    responses.add(
        responses.GET,
        url,
        json={"message": "Resource not accessible by integration"},
        status=403,
        headers={"X-RateLimit-Remaining": "999"},
    )

    response = github_signals.github_session_get(build_github_session("gh-token"), url)

    assert response.status_code == 403
    assert len(responses.calls) == 1


@responses.activate
def test_session_get_wraps_transport_failure_as_acquisition_error():
    url = "https://api.github.com/repos/canonical/example/topics"
    responses.add(responses.GET, url, body=requests.ConnectionError("network unavailable"))

    with pytest.raises(GitHubAcquisitionError) as exc_info:
        github_signals.github_session_get(build_github_session("gh-token"), url)

    assert exc_info.value.status_code == 0
    assert exc_info.value.url == url


@responses.activate
def test_repo_file_exists_true():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/contents/README.md",
        json={"name": "README.md"},
        status=200,
    )
    assert repo_file_exists("canonical/example", "README.md", "gh-token") is True


@pytest.mark.parametrize("status", [401, 403, 429, 500])
@responses.activate
def test_repo_file_exists_raises_when_required_evidence_acquisition_fails(status):
    url = "https://api.github.com/repos/canonical/example/contents/README.md"
    responses.add(responses.GET, url, json={"message": "failure"}, status=status)
    if status in {401, 429}:
        responses.add(responses.GET, url, json={"message": "failure"}, status=status)

    with pytest.raises(GitHubAcquisitionError):
        repo_file_exists("canonical/example", "README.md", "gh-token")


@responses.activate
def test_repo_file_exists_preserves_successful_absence_semantics():
    url = "https://api.github.com/repos/canonical/example/contents/README.md"
    responses.add(responses.GET, url, json={"message": "Not Found"}, status=404)
    responses.add(responses.GET, url, json={"message": "Not Found"}, status=404)

    assert repo_file_exists("canonical/example", "README.md", "gh-token") is False


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"message": "server error"}, 500),
        ({}, 200),
        ({"encoding": "base64", "content": "%%%"}, 200),
        (["not", "a", "file"], 200),
    ],
)
@responses.activate
def test_repo_file_text_raises_when_content_cannot_be_acquired(payload, status):
    url = "https://api.github.com/repos/canonical/example/contents/README.md"
    responses.add(responses.GET, url, json=payload, status=status)

    with pytest.raises(GitHubAcquisitionError):
        repo_file_text("canonical/example", "README.md", None)


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


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"message": "server error"}, 500),
        ({}, 200),
        ({"total_count": "many"}, 200),
    ],
)
@responses.activate
def test_search_code_count_raises_when_search_evidence_cannot_be_acquired(payload, status):
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        json=payload,
        status=status,
    )

    with pytest.raises(GitHubAcquisitionError):
        search_code_count("repo:canonical/example import jubilant", None)


@responses.activate
def test_search_code_count_wraps_transport_failure():
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        body=requests.ConnectionError("network unavailable"),
    )

    with pytest.raises(GitHubAcquisitionError):
        search_code_count("repo:canonical/example import jubilant", None)


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
def test_workflow_files_preserves_absent_directory_semantics():
    url = "https://api.github.com/repos/canonical/example/contents/.github/workflows"
    responses.add(responses.GET, url, json={"message": "Not Found"}, status=404)

    assert workflow_files("canonical/example", None) == []


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"message": "server error"}, 500),
        ({"entries": []}, 200),
        ([{"type": "file", "name": 42}], 200),
    ],
)
@responses.activate
def test_workflow_files_raises_when_listing_cannot_be_acquired(payload, status):
    url = "https://api.github.com/repos/canonical/example/contents/.github/workflows"
    responses.add(responses.GET, url, json=payload, status=status)

    with pytest.raises(GitHubAcquisitionError):
        workflow_files("canonical/example", None)


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"message": "server error"}, 500),
        ({"encoding": "base64", "content": "%%%"}, 200),
    ],
)
@responses.activate
def test_workflow_files_raises_when_listed_file_cannot_be_acquired(payload, status):
    listing_url = "https://api.github.com/repos/canonical/example/contents/.github/workflows"
    file_url = f"{listing_url}/ci.yaml"
    responses.add(
        responses.GET,
        listing_url,
        json=[{"type": "file", "name": "ci.yaml", "url": file_url}],
        status=200,
    )
    responses.add(responses.GET, file_url, json=payload, status=status)

    with pytest.raises(GitHubAcquisitionError):
        workflow_files("canonical/example", None)


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


@pytest.mark.parametrize(
    ("url_suffix", "payload", "status"),
    [
        ("", {"message": "server error"}, 500),
        ("", {}, 200),
        ("/branches/main", {"message": "server error"}, 500),
        ("/branches/main", {"commit": {}}, 200),
        ("/commits/abc123/check-runs", {"message": "server error"}, 500),
        ("/commits/abc123/check-runs", {"checks": []}, 200),
    ],
)
@responses.activate
def test_default_branch_check_runs_raises_on_incomplete_acquisition(url_suffix, payload, status):
    repo_url = "https://api.github.com/repos/canonical/example"
    if url_suffix:
        responses.add(
            responses.GET,
            repo_url,
            json={"default_branch": "main"},
            status=200,
        )
    if url_suffix.startswith("/commits/"):
        responses.add(
            responses.GET,
            f"{repo_url}/branches/main",
            json={"commit": {"sha": "abc123"}},
            status=200,
        )
    responses.add(responses.GET, f"{repo_url}{url_suffix}", json=payload, status=status)

    with pytest.raises(GitHubAcquisitionError):
        default_branch_check_runs("canonical/example", None)


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"message": "server error"}, 500),
        ({"releases": []}, 200),
    ],
)
@responses.activate
def test_repo_releases_raises_when_release_evidence_cannot_be_acquired(payload, status):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/example/releases",
        json=payload,
        status=status,
    )

    with pytest.raises(GitHubAcquisitionError):
        repo_releases("canonical/example", None)
