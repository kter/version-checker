resource "aws_sqs_queue" "scan_jobs_dlq" {
  name = "${var.project}-${var.env}-scan-jobs-dlq"

  tags = {
    Environment = var.env
  }
}

resource "aws_sqs_queue" "scan_jobs" {
  name                       = "${var.project}-${var.env}-scan-jobs"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.scan_jobs_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Environment = var.env
  }
}
