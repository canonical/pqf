from tools.import_platform_engineering_docs_products import (
    _convert_docs_product,
    _parse_github_source,
)


def test_parse_github_source_extracts_repo_and_subpath_from_monorepo_url():
    source = _parse_github_source(
        "https://github.com/canonical/http-proxy-operators/tree/main/squid-forward-proxy-operator"
    )
    assert source == {
        "repo": "canonical/http-proxy-operators",
        "subpath": "squid-forward-proxy-operator",
    }


def test_convert_docs_product_builds_root_with_inline_components_and_context_refs():
    raw = {
        "product": {
            "id": "http-proxy",
            "name": "HTTP Proxy",
            "service_level": "silver",
            "summary": "Proxy suite",
        },
        "ownership": {"squad": "APAC"},
        "links": [
            {
                "name": "End-user documentation",
                "url": "https://documentation.ubuntu.com/http-proxy/latest/",
            }
        ],
        "components": [
            {
                "name": "squid-forward-proxy",
                "role": "primary",
                "type": "machine-charm",
                "repository": "https://github.com/canonical/http-proxy-operators/tree/main/squid-forward-proxy-operator",
            },
            {
                "name": "http-proxy-policy",
                "role": "dependency",
                "type": "subordinate-charm",
                "repository": "https://github.com/canonical/http-proxy-operators/tree/main/http-proxy-policy-operator",
            },
        ],
    }

    product_id, converted = _convert_docs_product(raw)

    assert product_id == "http-proxy"
    assert converted["product_type"] == "root"
    assert converted["target_medal"] == "silver"
    assert converted["documentation_url"] == "https://documentation.ubuntu.com/http-proxy/latest/"
    assert converted["composed_of"] == [
        {
            "id": "http-proxy-squid-forward-proxy",
            "product_type": "charm",
            "source": {
                "repo": "canonical/http-proxy-operators",
                "subpath": "squid-forward-proxy-operator",
            },
            "target_medal": "silver",
        }
    ]
    assert converted["context_refs"] == [
        {
            "label": "Http Proxy Policy",
            "repo": "canonical/http-proxy-operators",
        }
    ]


def test_convert_docs_product_applies_non_github_source_override():
    raw = {
        "product": {"id": "mattermost", "name": "Mattermost", "service_level": "gold"},
        "ownership": {"squad": "Americas"},
        "components": [
            {
                "name": "mattermost",
                "role": "primary",
                "type": "k8s-charm",
                "repository": "https://code.launchpad.net/charm-k8s-mattermost",
            }
        ],
    }
    _, converted = _convert_docs_product(raw)
    assert converted["composed_of"][0]["source"] == {"repo": "canonical/mattermost-k8s-operator"}
