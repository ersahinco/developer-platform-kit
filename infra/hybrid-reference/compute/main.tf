locals {
  name = "${var.stack_name}-hybrid"
  labels = {
    project    = var.stack_name
    managed_by = "terraform"
    root       = "hybrid-compute"
    lane       = "starter"
  }
}

resource "hcloud_ssh_key" "operator" {
  name       = "${local.name}-operator"
  public_key = var.ssh_public_key
  labels     = local.labels
}

resource "hcloud_firewall" "runtime" {
  name   = "${local.name}-runtime"
  labels = local.labels

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.admin_cidrs
    description = "Operator SSH"
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "ACME HTTP challenge and redirect"
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "Origin HTTPS"
  }

  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "Path MTU and reachability"
  }
}

resource "hcloud_server" "runtime" {
  name         = local.name
  server_type  = var.server_type
  image        = var.server_image
  location     = var.server_location
  ssh_keys     = [hcloud_ssh_key.operator.id]
  firewall_ids = [hcloud_firewall.runtime.id]
  backups      = false
  labels       = local.labels
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    ssh_public_key = var.ssh_public_key
  })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }
}
