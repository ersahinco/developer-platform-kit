from pathlib import Path

from scripts.ci.iac_compatibility import _copy_root, plan_actions


def test_plan_actions_normalizes_tool_output() -> None:
    output = """
      # aws_s3_bucket.exports will be created
      # hcloud_server.runtime will be updated
      # cloudflare_dns_record.workload will be destroyed
    """

    assert plan_actions(output) == {
        ("aws_s3_bucket.exports", "created"),
        ("hcloud_server.runtime", "updated"),
        ("cloudflare_dns_record.workload", "destroyed"),
    }


def test_compatibility_copy_excludes_tool_specific_provider_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.tf").write_text('resource "example" "this" {}\n')
    (source / ".terraform.lock.hcl").write_text("tool-specific checksums\n")
    (source / ".terraform").mkdir()
    (source / ".terraform" / "provider").write_text("cached provider\n")

    destination = tmp_path / "destination"
    _copy_root(source, destination)

    assert (destination / "main.tf").is_file()
    assert not (destination / ".terraform").exists()
    assert not (destination / ".terraform.lock.hcl").exists()
