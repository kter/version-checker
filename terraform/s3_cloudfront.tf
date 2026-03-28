# ============================================
# S3 + CloudFront for Frontend (Static SPA)
# ============================================

# S3 Bucket for Frontend
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project}-${var.env}-frontend"

  tags = {
    Environment = var.env
  }
}

# IAM Policy for S3 Access (for deployment)
resource "aws_iam_policy" "s3_frontend_access" {
  name        = "${var.project}-${var.env}-s3-frontend-access"
  description = "Allows access to S3 frontend bucket for deployment"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.frontend.arn,
          "${aws_s3_bucket.frontend.arn}/*"
        ]
      }
    ]
  })
}

# Attach to IAM user "kter" (hardcoded for dev environment)
resource "aws_iam_user_policy_attachment" "s3_frontend_attachment" {
  count      = var.env == "dev" ? 1 : 0
  user       = "kter"
  policy_arn = aws_iam_policy.s3_frontend_access.arn
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Configuration
resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html" # SPA: all routes return index.html
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 Bucket Policy (Allow CloudFront and deployment access)
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      },
      # Allow AWS account users to deploy (for development)
      {
        Sid    = "AllowDeployment"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::848738341109:user/kter"
        }
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.frontend.arn,
          "${aws_s3_bucket.frontend.arn}/*"
        ]
      }
    ]
  })
}

# ACM Certificate (for custom domain)
# Note: Certificate must be in us-east-1 for CloudFront
# Get all certificates and filter by most recent wildcard certificate
data "aws_acm_certificate" "custom_domain" {
  count    = var.domain_name != "" ? 1 : 0
  domain   = "dev.devtools.site" # Search for base domain
  statuses = ["ISSUED"]
  provider = aws.us_east_1

  # Find the most recent certificate
  most_recent = true
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project}-${var.env}-frontend-oac"
  description                       = "OAC for ${var.project} ${var.env} frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = "PriceClass_100" # US, Canada, Europe (cheaper)
  default_root_object = "index.html"

  # Custom domain (optional)
  aliases = var.domain_name != "" ? [var.domain_name] : []

  # Viewer certificate
  viewer_certificate {
    acm_certificate_arn            = var.domain_name != "" ? data.aws_acm_certificate.custom_domain[0].arn : ""
    ssl_support_method             = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021"
    cloudfront_default_certificate = var.domain_name == ""
  }

  # Origins
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_id                = "S3-${aws_s3_bucket.frontend.id}"
  }

  # Default cache behavior (for static assets)
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = true
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400    # 24 hours
    max_ttl                = 31536000 # 1 year
    compress               = true
  }

  # SPA: Handle client-side routing
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Environment = var.env
  }
}

# ============================================
# Aliases for us-east-1 provider
# ============================================

provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.env == "local" ? "dev" : var.env
}
