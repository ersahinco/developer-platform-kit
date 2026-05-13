from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_source_tree_is_flat_and_importable_by_folder_name() -> None:
    expected_files = [
        ROOT / "apps" / "api" / "main.py",
        ROOT / "apps" / "backfill_worker" / "main.py",
        ROOT / "apps" / "data_export_job" / "main.py",
        ROOT / "apps" / "order_event_consumer" / "main.py",
        ROOT / "packages" / "domain" / "order.py",
        ROOT / "packages" / "application" / "order_submission.py",
        ROOT / "packages" / "infrastructure" / "db" / "repository.py",
    ]

    for path in expected_files:
        assert path.is_file()

    stale_paths = [
        ROOT / "apps" / "api" / "src",
        ROOT / "apps" / "backfill-worker",
        ROOT / "apps" / "data-export-job",
        ROOT / "apps" / "order-event-consumer",
        ROOT / "packages" / "domain" / "src",
        ROOT / "packages" / "application" / "src",
        ROOT / "packages" / "infrastructure" / "src",
    ]

    for path in stale_paths:
        assert not path.exists()

    tracked_files = subprocess.run(
        ["git", "ls-files", "apps", "packages"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert not [path for path in tracked_files if ".egg-info/" in path]


def test_repository_does_not_track_generated_or_placeholder_artifacts() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden_segments = [
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".venv/",
        ".terraform/",
        ".egg-info/",
        "/dist/",
        "/build/",
    ]
    forbidden_suffixes = [
        ".pyc",
        ".pyo",
        ".tmp",
        ".bak",
        ".swp",
        "~",
    ]

    offenders = [
        path
        for path in tracked_files
        if any(segment in f"{path}/" for segment in forbidden_segments)
        or any(path.endswith(suffix) for suffix in forbidden_suffixes)
    ]

    assert offenders == []

    placeholder_roots = [
        ROOT / "deploy",
        ROOT / "local",
        ROOT / "ops",
        ROOT / "security",
    ]

    for path in placeholder_roots:
        assert not path.exists()


def test_tracked_scripts_are_referenced_outside_themselves() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    script_paths = [
        path
        for path in tracked_files
        if path.startswith("scripts/")
        and Path(path).suffix in {".py", ".sh"}
        and Path(path).name != "__init__.py"
    ]
    reference_paths = [path for path in tracked_files if (ROOT / path).exists()]
    reference_paths = [
        path
        for path in reference_paths
        if path == "Makefile"
        or path == "README.md"
        or path.startswith((".github/", "docs/", "platform/", "scripts/", "tests/"))
    ]

    unreferenced_scripts = []
    for script_path in script_paths:
        script_name = Path(script_path).name
        references = []
        for reference_path in reference_paths:
            if reference_path == script_path:
                continue
            text = (ROOT / reference_path).read_text(encoding="utf-8")
            if script_path in text or script_name in text:
                references.append(reference_path)

        if not references:
            unreferenced_scripts.append(script_path)

    assert unreferenced_scripts == []


def test_platform_root_stays_bootstrap_and_github_oidc_only() -> None:
    platform_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "platform").glob("*.tf"))
    )
    forbidden_runtime_resources = [
        'resource "aws_ecs_',
        'resource "aws_db_',
        'resource "aws_rds_',
        'resource "aws_lb"',
        'resource "aws_lb_',
        'resource "aws_ecr_',
        'resource "aws_s3_bucket"',
        'resource "aws_sqs_',
        'resource "aws_sns_',
        'resource "aws_cloudwatch_',
        'resource "aws_scheduler_',
        'resource "aws_wafv2_',
    ]

    for forbidden in forbidden_runtime_resources:
        assert forbidden not in platform_tf


def test_app_root_consumes_platform_only_through_remote_state_outputs() -> None:
    providers_tf = (ROOT / "infra" / "app" / "providers.tf").read_text(encoding="utf-8")
    app_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "app").glob("*.tf"))
    )

    assert 'data "terraform_remote_state" "platform"' in providers_tf
    assert "platform = data.terraform_remote_state.platform.outputs" in providers_tf
    assert 'source  = "../platform"' not in app_tf
    assert "data.aws_vpc" not in app_tf
    assert "data.aws_subnets" not in app_tf


def test_terraform_state_uses_s3_native_lockfiles_only() -> None:
    versions_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ["infra/platform/versions.tf", "infra/app/versions.tf"]
    )
    state_docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in [
            "Makefile",
            "docs/deployment.md",
            "infra/platform/github_actions.tf",
        ]
    )

    assert versions_text.count("use_lockfile = true") == 2
    assert "dynamodb_table" not in versions_text
    assert "terraform-locks" not in state_docs
    assert "dynamodb:" not in state_docs
