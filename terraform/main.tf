terraform {
  required_version = ">= 1.5.0"
  
  backend "local" {
    # Using local backend for simplicity, but simulating a remote state via workspaces.
    path = "terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.env == "local" ? "dev" : var.env # Use dev profile for local testing

  default_tags {
    tags = {
      Project     = "VersionChecker"
      Environment = terraform.workspace
      ManagedBy   = "Terraform"
    }
  }
}

# Fetch caller identity for IAM policies
data "aws_caller_identity" "current" {}
