import responses

from scorers.shared.github_signals import (
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
