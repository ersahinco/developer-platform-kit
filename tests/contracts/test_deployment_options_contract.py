from __future__ import annotations

from ._helpers import read_text


def test_deployment_options_document_runtime_choice_without_new_runtime_target() -> (
    None
):
    doc = read_text("docs/deployment-options.md")
    runtime_defaults = read_text("platform/runtime-defaults.json")
    docs_index = read_text("docs/README.md")
    runtime_toolkit = read_text("docs/runtime-toolkit.md")

    assert "[Deployment Options](deployment-options.md)" in docs_index
    assert "[Deployment Options](deployment-options.md)" in runtime_toolkit
    assert '"aws-ecs"' in runtime_defaults
    assert '"supabase"' not in runtime_defaults.lower()

    assert "This page is guidance, not an active runtime target." in doc
    assert "ECS/Fargate compute plus AWS-managed dependencies" in doc
    assert "ECS/Fargate compute plus Supabase DB" in doc
    assert "Candidate platform-edge DB realization, not default" in doc
    assert "## Capability Impact" in doc
    assert "Deployment options are acceptable only when they realize the same" in doc
    assert "Current `aws-ecs` realization" in doc
    assert "Hybrid or brownfield realization question" in doc
    assert "Capability status:" in doc
    assert "Active: `local-compose`, `local-kubernetes`, and `aws-ecs`" in doc
    assert "Reference implementation: the Cloudflare/Hetzner/Supabase/S3" in doc
    assert "[Hybrid Starter Reference](hybrid-reference.md)" in doc
    assert "Outside active defaults until reviewed proof" in doc
    assert "bounded candidate" in doc
    assert "without claiming production readiness" in doc
    assert "## Decision Workflow" in doc
    assert "Promote anything to an active runtime target only after owner" in doc
    assert "fit before migration" in doc
    assert "Do not stack poolers by default." in doc
    assert "Candidate checklist:" in doc
    assert "Endpoint mode" in doc
    assert "IP family" in doc
    assert "Pooling" in doc
    assert "credential rotation paths are separated" in doc
    assert "Supabase documents PrivateLink for direct database and" in doc
    assert "network" in doc
    assert "restrictions" in doc
    assert "SSL settings" in doc
    assert "PrivateLink" in doc


def test_deployment_options_preserve_existing_proof_and_evidence_shape() -> None:
    doc = read_text("docs/deployment-options.md")

    for target in [
        "make workload-readiness-local",
        "make platform-toolkit-smoke-local",
        "make dapr-smoke",
        "make local-kubernetes-evidence-drill",
        "make workflow-dry-run-validate-gh",
        "make platform-toolkit-validate-cloud",
    ]:
        assert target in doc

    for evidence in [
        "Release event JSON/Markdown",
        "Network evidence",
        "Runtime evidence",
        "Data evidence",
        "Release evidence",
        "Secrets injection",
        "Observability routing",
        "rollback category",
        "outbox pending count",
    ]:
        assert evidence in doc


def test_deployment_options_link_official_vendor_sources() -> None:
    doc = read_text("docs/deployment-options.md")

    for source in [
        "docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html",
        "docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html",
        "docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html",
        "supabase.com/docs/guides/database/connecting-to-postgres",
        "supabase.com/docs/guides/platform/privatelink",
        "supabase.com/docs/guides/platform/ssl-enforcement",
    ]:
        assert source in doc
