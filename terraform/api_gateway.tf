locals {
  frontend_domain_name = var.env == "prd" ? "version-check.devtools.site" : "version-check.dev.devtools.site"
  api_domain_name      = var.env == "prd" ? "api.version-check.devtools.site" : "api.version-check.dev.devtools.site"
  hosted_zone_name     = var.env == "prd" ? "devtools.site." : "dev.devtools.site."

  frontend_certificate_lookup_domain = var.env == "prd" ? "devtools.site" : "dev.devtools.site"
  frontend_base_url                  = "https://${local.frontend_domain_name}"
  api_base_url                       = "https://${local.api_domain_name}"
  cors_allow_origins                 = ["http://localhost:3000", local.frontend_base_url]
}

data "aws_route53_zone" "app" {
  name         = local.hosted_zone_name
  private_zone = false
}

resource "aws_apigatewayv2_api" "backend" {
  name          = "${var.project}-${var.env}-backend-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "OPTIONS"]
    allow_origins     = local.cors_allow_origins
    expose_headers    = ["*"]
    max_age           = 3600
  }

  tags = {
    Environment = var.env
  }
}

resource "aws_apigatewayv2_integration" "backend" {
  api_id                 = aws_apigatewayv2_api.backend.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.backend.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "backend" {
  api_id    = aws_apigatewayv2_api.backend.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.backend.id}"
}

resource "aws_apigatewayv2_stage" "backend" {
  api_id      = aws_apigatewayv2_api.backend.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Environment = var.env
  }
}

resource "aws_lambda_permission" "backend_api_gateway" {
  statement_id  = "AllowExecutionFromHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.backend.execution_arn}/*/*"
}

resource "aws_acm_certificate" "api_domain" {
  domain_name       = local.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Environment = var.env
  }
}

resource "aws_route53_record" "api_domain_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api_domain.domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.app.zone_id
}

resource "aws_acm_certificate_validation" "api_domain" {
  certificate_arn         = aws_acm_certificate.api_domain.arn
  validation_record_fqdns = [for record in aws_route53_record.api_domain_validation : record.fqdn]
}

resource "aws_apigatewayv2_domain_name" "backend" {
  domain_name = local.api_domain_name

  domain_name_configuration {
    certificate_arn = aws_acm_certificate_validation.api_domain.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "backend" {
  api_id      = aws_apigatewayv2_api.backend.id
  domain_name = aws_apigatewayv2_domain_name.backend.id
  stage       = aws_apigatewayv2_stage.backend.id
}

resource "aws_route53_record" "api_alias_ipv4" {
  name    = local.api_domain_name
  type    = "A"
  zone_id = data.aws_route53_zone.app.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_apigatewayv2_domain_name.backend.domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.backend.domain_name_configuration[0].hosted_zone_id
  }
}

resource "aws_route53_record" "api_alias_ipv6" {
  name    = local.api_domain_name
  type    = "AAAA"
  zone_id = data.aws_route53_zone.app.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_apigatewayv2_domain_name.backend.domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.backend.domain_name_configuration[0].hosted_zone_id
  }
}
