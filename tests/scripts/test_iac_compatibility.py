from scripts.ci.iac_compatibility import plan_actions


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
