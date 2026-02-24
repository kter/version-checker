# ============================================
# Lambda Backend (FastAPI)
# ============================================

# Build the Lambda deployment package
data "archive_file" "backend_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../backend"  # Adjust path to your backend directory
  output_path = "${path.module}/backend_lambda.zip"

  # Exclude unnecessary files
  excludes = [
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    "*.pyc",
    ".coverage",
    "htmlcov",
    ".pytest_cache",
  ]
}

# IAM Role for Lambda
resource "aws_iam_role" "backend_lambda" {
  name = "${var.project}-${var.env}-backend-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.env
  }
}

# IAM Policy for Lambda to access DSQL and DynamoDB
resource "aws_iam_role_policy" "backend_lambda" {
  name = "${var.project}-${var.env}-backend-lambda-policy"
  role = aws_iam_role.backend_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
        ]
        Resource = aws_dynamodb_table.cache.arn
      },
      {
        Effect   = "Allow"
        Action   = [
          "rds-db:connect",
        ]
        Resource = aws_dsql_cluster.main.arn
      },
      # Allow Lambda to write logs
      {
        Effect   = "Allow"
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project}-${var.env}-backend*"
      },
    ]
  })
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "backend_lambda" {
  name              = "/aws/lambda/${var.project}-${var.env}-backend"
  retention_in_days = 7
}

# Lambda Function
resource "aws_lambda_function" "backend" {
  function_name = "${var.project}-${var.env}-backend"
  description   = "Version Checker Backend API (FastAPI)"

  # Source code archive
  filename         = data.archive_file.backend_lambda.output_path
  source_code_hash = data.archive_file.backend_lambda.output_base64sha256

  # Runtime configuration
  runtime          = "python3.12"
  handler          = "lambda_handler.lambda_handler"
  role             = aws_iam_role.backend_lambda.arn

  # Environment variables
  environment {
    variables = {
      ENV              = var.env
      DSQL_ENDPOINT    = aws_dsql_cluster.main.arn
      DYNAMO_TABLE     = aws_dynamodb_table.cache.name
      GITHUB_CLIENT_ID = var.github_client_id
      GITHUB_CLIENT_SECRET = var.github_client_secret
      # Note: AWS_REGION is reserved by Lambda, use default region
    }
  }

  # Configuration
  timeout     = 30
  memory_size = 256

  tags = {
    Environment = var.env
  }

  depends_on = [aws_cloudwatch_log_group.backend_lambda]
}

# Lambda Function URL (Direct HTTPS access)
resource "aws_lambda_function_url" "backend" {
  function_name      = aws_lambda_function.backend.function_name
  authorization_type = "NONE"  # Add auth via API Gateway if needed

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }
}
