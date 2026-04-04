# ============================================
# Lambda Backend (FastAPI)
# ============================================

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
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.cache.arn,
          aws_dynamodb_table.repo_cache.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dsql:DbConnect",
          "dsql:DbConnectAdmin",
        ]
        Resource = aws_dsql_cluster.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
        ]
        Resource = aws_sqs_queue.scan_jobs.arn
      },
      # Allow Lambda to write logs
      {
        Effect = "Allow"
        Action = [
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
  filename         = "${path.module}/backend_lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/backend_lambda.zip")

  # Runtime configuration
  runtime = "python3.12"
  handler = "lambda_handler.lambda_handler"
  role    = aws_iam_role.backend_lambda.arn

  # Environment variables
  environment {
    variables = {
      ENV                    = var.env
      DSQL_ENDPOINT          = aws_dsql_cluster.main.arn
      DYNAMO_TABLE           = aws_dynamodb_table.cache.name
      REPO_CACHE_TABLE       = aws_dynamodb_table.repo_cache.name
      REPO_CACHE_TTL_SECONDS = "180"
      GITHUB_CLIENT_ID       = var.github_client_id
      GITHUB_CLIENT_SECRET   = var.github_client_secret
      FRONTEND_BASE_URL      = local.frontend_base_url
      CORS_ALLOW_ORIGINS     = join(",", local.cors_allow_origins)
      SCAN_QUEUE_URL         = aws_sqs_queue.scan_jobs.url
      # Note: AWS_REGION is reserved by Lambda, use default region
    }
  }

  # Configuration
  timeout     = 30
  memory_size = 512

  tags = {
    Environment = var.env
  }

  depends_on = [aws_cloudwatch_log_group.backend_lambda]
}

# Lambda Function URL (Direct HTTPS access)
resource "aws_lambda_function_url" "backend" {
  function_name      = aws_lambda_function.backend.function_name
  authorization_type = "NONE" # Add auth via API Gateway if needed

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }
}

resource "aws_iam_role" "scan_worker_lambda" {
  name = "${var.project}-${var.env}-scan-worker-lambda-role"

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

resource "aws_iam_role_policy" "scan_worker_lambda" {
  name = "${var.project}-${var.env}-scan-worker-lambda-policy"
  role = aws_iam_role.scan_worker_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.cache.arn,
          aws_dynamodb_table.repo_cache.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dsql:DbConnect",
          "dsql:DbConnectAdmin",
        ]
        Resource = aws_dsql_cluster.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:ReceiveMessage",
          "sqs:SendMessage",
        ]
        Resource = aws_sqs_queue.scan_jobs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project}-${var.env}-scan-worker*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "scan_worker_lambda" {
  name              = "/aws/lambda/${var.project}-${var.env}-scan-worker"
  retention_in_days = 7
}

resource "aws_lambda_function" "scan_worker" {
  function_name = "${var.project}-${var.env}-scan-worker"
  description   = "Version Checker Async Scan Worker"

  filename         = "${path.module}/backend_lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/backend_lambda.zip")

  runtime = "python3.12"
  handler = "app.scan_worker_handler.lambda_handler"
  role    = aws_iam_role.scan_worker_lambda.arn

  environment {
    variables = {
      ENV                    = var.env
      DSQL_ENDPOINT          = aws_dsql_cluster.main.arn
      DYNAMO_TABLE           = aws_dynamodb_table.cache.name
      REPO_CACHE_TABLE       = aws_dynamodb_table.repo_cache.name
      REPO_CACHE_TTL_SECONDS = "180"
      GITHUB_CLIENT_ID       = var.github_client_id
      GITHUB_CLIENT_SECRET   = var.github_client_secret
      FRONTEND_BASE_URL      = local.frontend_base_url
      CORS_ALLOW_ORIGINS     = join(",", local.cors_allow_origins)
      SCAN_QUEUE_URL         = aws_sqs_queue.scan_jobs.url
    }
  }

  timeout     = 120
  memory_size = 512

  tags = {
    Environment = var.env
  }

  depends_on = [aws_cloudwatch_log_group.scan_worker_lambda]
}

resource "aws_lambda_event_source_mapping" "scan_jobs" {
  event_source_arn = aws_sqs_queue.scan_jobs.arn
  function_name    = aws_lambda_function.scan_worker.arn
  batch_size       = 1
  enabled          = true
}
