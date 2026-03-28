resource "aws_dynamodb_table" "cache" {
  name         = "${var.project}-${var.env}-eol-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "${var.project}-${var.env}-eol-cache"
  }
}

resource "aws_iam_policy" "dynamodb_access" {
  name        = "${var.project}-${var.env}-dynamodb-access"
  description = "Allows access to the DynamoDB cache table"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.cache.arn
      }
    ]
  })
}

# Attach to the caller identity
resource "aws_iam_user_policy_attachment" "dynamo_attachment" {
  count      = length(regexall("user/(.*)", data.aws_caller_identity.current.arn)) > 0 ? 1 : 0
  user       = regex("user/(.*)", data.aws_caller_identity.current.arn)[0]
  policy_arn = aws_iam_policy.dynamodb_access.arn
}
