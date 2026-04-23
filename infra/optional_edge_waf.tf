################################################################################
# Optional edge security
#
# WAF improves the public edge but is intentionally separated from the lean base
# entry path of ALB + ACM + Route 53. It remains enabled by default so this
# phase changes structure, not deployed behavior.
################################################################################

resource "aws_wafv2_web_acl" "this" {
  name  = local.name
  scope = "REGIONAL"
  tags  = local.tags

  default_action {
    allow {}
  }

  # ── Rule 1: Rate limiting ─────────────────────────────────────────────────
  # Block IPs that exceed 100 requests in any 5-minute window.
  # 100 req/5min is generous for manual/CI use but stops credential stuffing
  # and scanner floods. AWS evaluates the window as a rolling 5-minute period.
  rule {
    name     = "RateLimit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 100
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 2: AWS Managed — Common Rule Set ─────────────────────────────────
  # Covers OWASP Top 10 categories: SQLi, XSS, bad HTTP requests, oversized
  # bodies, and known bad user agents. Count mode is not used — block directly.
  rule {
    name     = "CommonRuleSet"
    priority = 2

    override_action {
      none {} # use the rule group's own actions (block/count per rule)
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 3: AWS Managed — Known Bad Inputs ────────────────────────────────
  # Blocks requests matching known exploit patterns: Log4j JNDI lookups,
  # Spring4Shell, JavaDeserialisation probes, and SSRF attempts.
  rule {
    name     = "KnownBadInputs"
    priority = 3

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
      metric_name                = "${local.name}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = local.name
    sampled_requests_enabled   = true
  }
}

# Associate the Web ACL with the ALB.
# WAF evaluation happens before the ALB listener rules — a blocked request
# never reaches the fixed-token auth check or the app.
resource "aws_wafv2_web_acl_association" "this" {
  resource_arn = aws_lb.this.arn
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}
