################################################################################
# Edge — ALB, WAF, DNS, certificates, and routing
################################################################################

resource "aws_security_group" "alb" {
  # name_prefix instead of name: description changes force SG replacement.
  # name_prefix lets AWS generate a unique name so create_before_destroy can
  # create the new SG before destroying the old one — a fixed name would cause
  # a duplicate-name collision in the same VPC.
  name_prefix = "${local.name}-alb-"
  description = "ALB: HTTPS from internet only, egress to app tasks"
  vpc_id      = local.platform.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.alb_ingress_cidr]
  }

  # Port 80 removed — callers connect directly on HTTPS. No redirect listener.

  egress {
    description = "All egress to app tasks"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "app" {
  # name_prefix + create_before_destroy: same reason as alb SG — description
  # changes force replacement and a fixed name collides in the same VPC.
  name_prefix = "${local.name}-app-"
  description = "App tasks: inbound from ALB only, HTTPS egress to AWS APIs, Postgres to RDS"
  vpc_id      = local.platform.vpc_id

  lifecycle {
    create_before_destroy = true
    # Optional observability scrape ingress is managed as a standalone rule to
    # avoid an app SG <-> observability SG dependency cycle.
    ignore_changes = [ingress]
  }

  ingress {
    description     = "From ALB on container port"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Egress: HTTPS to anywhere covers both VPC Interface Endpoints (ECR, Secrets
  # Manager, CloudWatch Logs, SSM) and the S3 Gateway Endpoint (ECR layers).
  # Restricting to vpc_cidr breaks tasks in AZs where an endpoint ENI is absent —
  # the task resolves ECR to a public IP and the connection times out with no NAT path.
  # The meaningful security boundary is IAM + ingress rules, not egress CIDR.
  egress {
    description = "HTTPS to AWS APIs (VPC endpoints + fallback)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # RDS is in intra subnets — Postgres egress stays scoped to the VPC CIDR.
  egress {
    description = "Postgres to RDS in intra subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [local.vpc_cidr]
  }

  egress {
    description = "Loki log delivery in private observability stack"
    from_port   = 3100
    to_port     = 3100
    protocol    = "tcp"
    cidr_blocks = [local.vpc_cidr]
  }

  egress {
    description = "Tempo OTLP trace delivery in private observability stack"
    from_port   = 4318
    to_port     = 4318
    protocol    = "tcp"
    cidr_blocks = [local.vpc_cidr]
  }

  tags = local.tags
}

resource "aws_lb" "this" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.platform.public_subnet_ids

  access_logs {
    bucket  = local.observability_bucket_name
    prefix  = "alb-access-logs"
    enabled = true
  }

  # Drop invalid HTTP headers — prevents header smuggling attacks at no cost.
  drop_invalid_header_fields = true
  tags                       = local.tags

  depends_on = [aws_s3_bucket_policy.observability_alb_access_logs]
}

resource "aws_wafv2_web_acl" "edge" {
  name        = "${local.name}-edge"
  description = "Managed-rule WAF protection for the public API ALB"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-waf-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-waf-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-waf"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

resource "aws_wafv2_web_acl_association" "edge_alb" {
  resource_arn = aws_lb.this.arn
  web_acl_arn  = aws_wafv2_web_acl.edge.arn
}

resource "aws_lb_target_group" "app" {
  name        = local.name
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = local.platform.vpc_id
  target_type = "ip" # required for Fargate — each task gets its own ENI

  # 5s: faster than the default 300s. Keep above 0 — ECS needs a moment to
  # deregister the task from the ALB before the rolling update completes.
  deregistration_delay = 5

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    # 5s interval: 2 consecutive successes = ~10s after task is healthy.
    # Default is 30s (60s to mark healthy) — this alone saves ~50s per deploy.
    interval = 5
    timeout  = 3
    matcher  = "200"
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "app_unhealthy_targets" {
  alarm_name          = "${local.name}-app-unhealthy-targets"
  alarm_description   = "ALB reports unhealthy app targets. Runbook: docs/runbooks/app-service-unhealthy.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 0
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  unit                = "Count"

  dimensions = {
    LoadBalancer = aws_lb.this.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "app_target_5xx" {
  count = var.enable_app_symptom_cloudwatch_alarms ? 1 : 0

  alarm_name          = "${local.name}-app-target-5xx"
  alarm_description   = "App targets returned 5xx responses behind the ALB. Runbook: docs/runbooks/app-edge-errors-latency.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 0
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  unit                = "Count"

  dimensions = {
    LoadBalancer = aws_lb.this.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "app_target_latency" {
  count = var.enable_app_symptom_cloudwatch_alarms ? 1 : 0

  alarm_name          = "${local.name}-app-target-latency"
  alarm_description   = "App target p95 response time exceeded 2 seconds. Runbook: docs/runbooks/app-edge-errors-latency.md"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  treat_missing_data  = "notBreaching"
  unit                = "Seconds"

  dimensions = {
    LoadBalancer = aws_lb.this.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }

  tags = local.tags
}

resource "aws_acm_certificate" "api" {
  domain_name       = local.api_fqdn
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = local.tags
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = local.platform.route53_public_zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]
}

################################################################################
# HTTPS listener — fixed-token auth on all routes.
# The ALB evaluates rules top-to-bottom. Rule 1 checks the Authorization header
# against the token stored in Secrets Manager. Any request without the exact
# header value receives a 401 before it reaches the app.
################################################################################

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn

  # Default action: deny — safety net for any request that misses rule 1.
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = "{\"detail\":\"Unauthorized\"}"
      status_code  = "401"
    }
  }
}

resource "aws_lb_listener_rule" "auth" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 1

  # Match all paths — auth applies to every route.
  condition {
    path_pattern {
      values = ["/*"]
    }
  }

  # Forward only if the Authorization header matches the token exactly.
  # ALB evaluates both conditions with AND logic — path AND header must match.
  condition {
    http_header {
      http_header_name = "Authorization"
      values           = ["Bearer ${data.aws_secretsmanager_secret_version.api_token.secret_string}"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_route53_record" "api_alias" {
  zone_id = local.platform.route53_public_zone_id
  name    = local.api_fqdn
  type    = "A"

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}
