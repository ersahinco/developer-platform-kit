################################################################################
# Application load balancer
#
# One ALB per edge, shared by the services behind it. HTTP exists only to
# redirect to HTTPS when a certificate is present. Access logs are on by
# default: they are the only record of a request that never reached a task.
################################################################################

locals {
  https_enabled = var.certificate_arn != null
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  description = "Ingress to the ${var.name} load balancer"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  for_each = toset(local.https_enabled ? var.allowed_cidr_blocks : [])

  security_group_id = aws_security_group.alb.id
  description       = "HTTP redirect to HTTPS"
  cidr_ipv4         = each.value
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  for_each = toset(local.https_enabled ? var.allowed_cidr_blocks : [])

  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from allowed clients"
  cidr_ipv4         = each.value
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "http_only" {
  for_each = toset(local.https_enabled ? [] : var.allowed_cidr_blocks)

  security_group_id = aws_security_group.alb.id
  description       = "HTTP from allowed clients, no certificate configured"
  cidr_ipv4         = each.value
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "to_targets" {
  security_group_id = aws_security_group.alb.id
  description       = "Load balancer to targets inside the VPC"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

# This is the public edge when internal=false; public plaintext is guarded below.
# trivy:ignore:AVD-AWS-0053
resource "aws_lb" "this" {
  # checkov:skip=CKV2_AWS_20:Conditional HTTP redirect follows certificate_arn; public plaintext requires explicit allow_public_http.
  # checkov:skip=CKV2_AWS_28:WAF rules and their ongoing cost are owned by the public application's security requirements.

  name               = var.name
  internal           = var.internal
  load_balancer_type = "application"
  subnets            = var.subnet_ids
  security_groups    = [aws_security_group.alb.id]

  drop_invalid_header_fields = true
  enable_deletion_protection = var.enable_deletion_protection
  idle_timeout               = var.idle_timeout

  dynamic "access_logs" {
    for_each = var.access_logs_bucket == null ? [] : [1]
    content {
      bucket  = var.access_logs_bucket
      prefix  = var.name
      enabled = true
    }
  }

  tags = var.tags

  lifecycle {
    precondition {
      condition     = var.internal || var.certificate_arn != null || var.allow_public_http
      error_message = "An internet-facing load balancer without a certificate serves plaintext. Pass certificate_arn, or set allow_public_http to accept that."
    }
  }
}

# Redirects to HTTPS when configured; public plaintext requires allow_public_http.
# trivy:ignore:AVD-AWS-0054
resource "aws_lb_listener" "http" {
  # checkov:skip=CKV_AWS_103:HTTP redirects to the TLS 1.2+ listener when a certificate exists; public plaintext requires explicit opt-in.

  # checkov:skip=CKV_AWS_2:HTTP redirects to HTTPS when a certificate is supplied; public plaintext requires explicit allow_public_http.

  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = local.https_enabled ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = local.https_enabled ? [] : [1]
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.default.arn
    }
  }

  tags = var.tags
}

resource "aws_lb_listener" "https" {
  count = local.https_enabled ? 1 : 0

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.default.arn
  }

  tags = var.tags
}

resource "aws_lb_target_group" "default" {
  # checkov:skip=CKV_AWS_378:TLS terminates at the ALB; HTTP targets are private Fargate tasks restricted to the ALB security group.

  name        = "${var.name}-default"
  port        = var.target_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  deregistration_delay = var.deregistration_delay

  health_check {
    path                = var.health_check_path
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}
