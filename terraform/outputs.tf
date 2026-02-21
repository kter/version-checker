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
