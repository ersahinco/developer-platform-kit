from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docs_do_not_describe_stale_core_adapter_or_direct_sqs_model() -> None:
    paths = [
        ROOT / "README.md",
        *sorted((ROOT / ".github" / "workflows").rglob("*.yml")),
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "db").rglob("*.yaml")),
        *sorted((ROOT / "tests").rglob("*.py")),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    forbidden_terms = [
        "/".join(("packages", "core")),
        "/".join(("packages", "adapters")),
        "_".join(("aws", "sdlc", "core")),
        "_".join(("aws", "sdlc", "adapters")),
        " ".join(("SQS", "publish")),
        " ".join(("SQS", "publishing")),
        "-".join(("SQS", "backed")) + " order event",
    ]

    for forbidden in forbidden_terms:
        assert forbidden not in text


def test_docs_position_project_as_toolkit_not_private_framework() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    platform_contract = (ROOT / "docs" / "platform-contract.md").read_text(
        encoding="utf-8"
    )
    workload_toolkit = (ROOT / "docs" / "workload-toolkit.md").read_text(
        encoding="utf-8"
    )

    assert "opinionated cloud-native delivery toolkit" in readme
    assert "does not try to replace proven tools" in readme
    assert "not a private application framework" in readme
    assert "opinionated platform toolkit, not a private framework" in platform_contract
    assert "standardization without reinvention" in workload_toolkit


def test_docs_have_one_grouped_index_instead_of_duplicate_maps() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    architecture_layout = (ROOT / "docs" / "architecture-layout.md").read_text(
        encoding="utf-8"
    )
    roadmap = (ROOT / "docs" / "roadmaps.md").read_text(encoding="utf-8")

    assert "For the grouped documentation map, use [docs/README.md]" in readme
    assert "## Docs By Job" not in readme
    assert "This is the canonical map for project docs" in docs_index
    assert "ubiquitous-language.md" in docs_index
    assert "in `docs/README.md`; keep detailed ownership there" in architecture_layout
    assert "Keep detailed ownership in `docs/README.md`" in roadmap


def test_docs_define_ubiquitous_language_for_agents_and_humans() -> None:
    language = (ROOT / "docs" / "ubiquitous-language.md").read_text(encoding="utf-8")
    engineering_loop = (ROOT / "docs" / "engineering-loop.md").read_text(
        encoding="utf-8"
    )

    for phrase in [
        "opinionated cloud-native delivery toolkit",
        "Platform toolkit",
        "Workload",
        "Runtime target",
        "Provider edge",
        "Contract",
        "Conformance",
        "Release evidence",
        "`apps/*`",
        "`packages/domain`",
        "`packages/application`",
        "`packages/infrastructure`",
        "Portable observability baseline",
        "PostgreSQL-compatible contract",
        'platform toolkit", not "custom framework',
        'runtime target", not "cloud abstraction',
    ]:
        assert phrase in language

    assert "Use [Ubiquitous Language](ubiquitous-language.md)" in engineering_loop


def test_canonical_docs_do_not_contain_session_prompt_blocks() -> None:
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "README.md",
            *sorted((ROOT / "docs").rglob("*.md")),
        ]
    )

    forbidden_terms = [
        "\n## Prompt\n",
        "You are working in the aws-sdlc-containers repo.",
        "Start by reading:",
        "Evaluate critically:",
        "Current known remaining gaps to consider:",
        "Grafana Cloud AI",
        "Grafana Assistant",
        "Assistant-style",
        "Bitbucket Pipelines",
        "# Observability Plan",
        "# Data Flow Plan",
    ]

    for forbidden in forbidden_terms:
        assert forbidden not in docs


def test_documentation_inventory_keeps_canonical_docs_linked() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    top_level_docs = sorted((ROOT / "docs").glob("*.md"))

    assert "(docs/README.md)" in readme

    missing_from_docs_index = [
        str(path.relative_to(ROOT))
        for path in top_level_docs
        if path.name != "README.md" and f"({path.name})" not in docs_index
    ]

    assert missing_from_docs_index == []

    for collection in ["runbooks", "drills"]:
        index = (ROOT / "docs" / collection / "README.md").read_text(encoding="utf-8")
        child_docs = sorted(
            path
            for path in (ROOT / "docs" / collection).glob("*.md")
            if path.name != "README.md"
        )
        missing_from_index = [
            str(path.relative_to(ROOT))
            for path in child_docs
            if f"({path.name})" not in index
        ]

        assert missing_from_index == []


def _headings(markdown: str) -> set[str]:
    return {
        line.strip()
        for line in markdown.splitlines()
        if line.startswith("#") and line.strip()
    }


def test_toolkit_docs_keep_pragmatic_sections() -> None:
    expected_headings = {
        "docs/platform-contract.md": {
            "# Platform Contract",
            "## Workload Shape",
            "## Configuration And Secrets",
            "## Observability",
            "## Delivery And Evidence",
            "## Rollback",
            "## Toolkit Boundaries",
        },
        "docs/workload-toolkit.md": {
            "# Workload Toolkit",
            "## Required Shape",
            "## Boundary Rules",
            "## Checklist",
            "## Related Edges",
        },
        "docs/runtime-toolkit.md": {
            "# Runtime Toolkit",
            "## Entry Criteria",
            "## Required Capabilities",
            "## Current AWS ECS Target",
            "## Implementation Steps",
            "## Exit Criteria",
        },
        "docs/data.md": {
            "# Data",
            "## Current Flow",
            "## Database Contract",
            "## Data Export Job",
            "## Object Storage Contract",
            "## Deferred",
        },
        "docs/portability-status.md": {
            "# Portability Status",
            "## Portable Baseline",
            "## Intentional Provider Dependencies",
            "## Current Gaps",
            "## Practical Status",
        },
    }

    for path, headings in expected_headings.items():
        assert headings <= _headings((ROOT / path).read_text(encoding="utf-8"))


def test_portability_contracts_have_machine_readable_enforcement() -> None:
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    app_build = (ROOT / ".github" / "workflows" / "app-build.yml").read_text(
        encoding="utf-8"
    )

    for path in [
        ROOT / "platform" / "workloads.json",
        ROOT / "platform" / "runtime-capabilities.json",
        ROOT / "scripts" / "ci" / "validate_platform_contract.py",
    ]:
        assert path.is_file()

    for link in [
        "platform-contract.md",
        "workload-toolkit.md",
        "runtime-toolkit.md",
        "data.md",
        "dapr-portability-contract.md",
        "config-secrets-contract.md",
        "observability-onboarding-contract.md",
        "ci-quality-contract.md",
    ]:
        assert link in docs_index

    assert app_build.count('- "platform/**"') == 2
    assert "uv run python scripts/ci/validate_platform_contract.py" in app_build
