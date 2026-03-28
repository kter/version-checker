variable "aws_region" {
  description = "The AWS region to deploy into"
  type        = string
  default     = "ap-northeast-1"
}

variable "env" {
  description = "The deployment environment (dev, prd)"
  type        = string
  default     = "dev"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "version-checker"
}

variable "github_client_id" {
  description = "GitHub OAuth Client ID"
  type        = string
  default     = ""

  validation {
    condition     = var.env == "local" || trimspace(var.github_client_id) != ""
    error_message = "github_client_id must be set for dev and prd deployments."
  }
}

variable "github_client_secret" {
  description = "GitHub OAuth Client Secret (should use Secrets Manager in production)"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = var.env == "local" || trimspace(var.github_client_secret) != ""
    error_message = "github_client_secret must be set for dev and prd deployments."
  }
}

variable "domain_name" {
  description = "Custom domain name (optional)"
  type        = string
  default     = "version-check.dev.devtools.site"
}
