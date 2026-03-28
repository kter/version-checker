output "dsql_endpoint" {
  description = "The ARN/identifier of the Amazon Aurora DSQL cluster"
  value       = aws_dsql_cluster.main.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB cache table"
  value       = aws_dynamodb_table.cache.name
}

output "env" {
  value = var.env
}

output "lambda_backend_url" {
  description = "The URL of the Lambda Backend API"
  value       = aws_lambda_function_url.backend.function_url
}

output "api_gateway_url" {
  description = "The default invoke URL of the backend HTTP API"
  value       = aws_apigatewayv2_stage.backend.invoke_url
}

output "api_base_url" {
  description = "The custom-domain base URL for the backend API"
  value       = local.api_base_url
}

output "frontend_base_url" {
  description = "The public frontend base URL"
  value       = local.frontend_base_url
}

output "cloudfront_distribution_id" {
  description = "The ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_domain" {
  description = "The domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "s3_bucket_name" {
  description = "The name of the S3 bucket for frontend"
  value       = aws_s3_bucket.frontend.id
}
