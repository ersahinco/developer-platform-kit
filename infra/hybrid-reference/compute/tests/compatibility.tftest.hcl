mock_provider "hcloud" {
  override_resource {
    target = hcloud_firewall.runtime
    values = { id = 1001 }
  }

  override_resource {
    target = hcloud_ssh_key.operator
    values = { id = 1002 }
  }
}

run "starter_compute_plan" {
  command = plan

  variables {
    stack_name     = "compatibility-proof"
    ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICompatibilityProofOnly"
    admin_cidrs    = ["192.0.2.10/32"]
  }

  assert {
    condition     = hcloud_server.runtime.name == "compatibility-proof-hybrid"
    error_message = "The Hetzner server address or intent changed."
  }

  assert {
    condition     = hcloud_firewall.runtime.name == "compatibility-proof-hybrid-runtime"
    error_message = "The Hetzner firewall address or intent changed."
  }
}
