import pytest
import requests
import responses

from scorers.shared import github_signals
from scorers.shared.github_signals import (
    GitHubAcquisitionError,
    GitHubPermissionError,
    build_github_session,
    default_branch_check_runs,
    github_get,
    raise_for_required_github_evidence,
    repo_file_exists,
    repo_topics,
    search_code_count,
    workflow_files,
)


@pytest.mark.parametrize(
    ("status", "message", "headers", "permission_denied"),
    [
        (403, "Resource not accessible by personal access token", {}, True),
        (403, "Resource not accessible by integration", {}, True),
        (403, "Must have admin rights to Repository.", {}, True),
        (403, "API rate limit exceeded", {"X-RateLimit-Remaining": "0"}, False),
        (403, "Resource not accessible by integration", {"Retry-After": "60"}, False),
        (403, "Forbidden", {}, False),
        (401, "Bad credentials", {}, False),
        (429, "Too many requests", {}, False),
        (500, "Internal server error", {}, False),
    ],
)
@responses.activate
def test_only_explicit_permission_denials_are_classified(
    status, message, headers, permission_denied
):
    url = "https://api.github.com/repos/canonical/example/branches/main/protection"
    responses.get(url, status=status, json={"message": message}, headers=headers)
    response = build_github_session("gh-token").get(url)

    with pytest.raises(GitHubAcquisitionError) as error:
        raise_for_required_github_evidence(response, url)

    assert isinstance(error.value, GitHubPermissionError) is permission_denied


@pytest.mark.parametrize("status", [403, 404])
@responses.activate
def test_github_get_preserves_authenticated_error_when_anonymous_access_fails(status):
    url = "https://api.github.com/repos/canonical/example/branches/main/protection"
    responses.get(url, status=status, json={"message": "Authenticated result"})
    responses.get(url, status=401, json={"message": "Requires authentication"})

    response = github_get(url, "gh-token")

    assert response.status_code == status
    assert response.json()["message"] == "Authenticated result"


@responses.activate
def test_github_get_can_still_read_public_evidence_outside_token_repository_scope():
    url = "https://api.github.com/repos/canonical/example/contents/README.md"
    responses.get(url, status=404)
    responses.get(url, json={"name": "README.md"})

    assert github_get(url, "gh-token").json() == {"name": "README.md"}


@pytest.mark.parametrize("use_session", [False, True])
@responses.activate
def test_rate_limit_retries_keep_authentication_and_honor_retry_after(mocker, use_session):
    url = "https://api.github.com/search/code"
    sleep = mocker.patch("time.sleep")
    responses.get(url, status=403, headers={"Retry-After": "60"})
    responses.get(url, json={"total_count": 1})

    response = (
        github_signals.github_session_get(build_github_session("gh-token"), url)
        if use_session
        else github_get(url, "gh-token")
    )

    assert response.json() == {"total_count": 1}
    sleep.assert_called_once_with(60)
    assert all(
        call.request.headers["Authorization"] == "token gh-token" for call in responses.calls
    )


@responses.activate
def test_primary_rate_limit_waits_until_reset(mocker):
    url = "https://api.github.com/repos/canonical/example/issues"
    mocker.patch("time.time", return_value=1000)
    sleep = mocker.patch("time.sleep")
    responses.get(
        url, status=403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1060"}
    )
    responses.get(url, json=[])

    assert github_get(url, "gh-token").json() == []
    sleep.assert_called_once_with(61)


@responses.activate
def test_rate_limit_retries_are_bounded_and_preserve_error(mocker):
    url = "https://api.github.com/search/code"
    sleep = mocker.patch("time.sleep")
    responses.get(url, status=429, headers={"Retry-After": "60"})

    response = github_get(url, "gh-token")

    assert response.status_code == 429
    assert len(responses.calls) == 4
    assert sleep.call_count == 3
    assert all(
        call.request.headers["Authorization"] == "token gh-token" for call in responses.calls
    )


@pytest.mark.parametrize("error", [requests.ConnectionError, requests.Timeout])
@responses.activate
def test_transient_connection_failures_retry_authenticated_request(mocker, error):
    url = "https://api.github.com/repos/canonical/example/contents/.github/workflows/ci.yml"
    sleep = mocker.patch("time.sleep")
    responses.get(url, body=error("Connection interrupted"))
    responses.get(url, json={"name": "ci.yml"})

    assert github_get(url, "gh-token").json() == {"name": "ci.yml"}
    sleep.assert_called_once_with(1)
    assert all(
        call.request.headers["Authorization"] == "token gh-token" for call in responses.calls
    )


@responses.activate
def test_exhausted_connection_retries_still_fail(mocker):
    url = "https://api.github.com/repos/canonical/example"
    sleep = mocker.patch("time.sleep")
    responses.get(url, body=requests.ConnectionError("Connection interrupted"))

    with pytest.raises(requests.ConnectionError, match="Connection interrupted"):
        github_get(url, "gh-token")

    assert len(responses.calls) == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


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
