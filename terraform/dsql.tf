resource "aws_dsql_cluster" "main" {
  deletion_protection_enabled = var.env == "prd" ? true : false
  tags = {
    Name = "${var.project}-${var.env}-dsql"
  }
}

# Example IAM Role for accessing DSQL from local
# (Assuming the local machine uses the profile credentials mapped to this role or user)
resource "aws_iam_policy" "dsql_access" {
  name        = "${var.project}-${var.env}-dsql-access"
  description = "Allows data access to the Aurora DSQL cluster"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "dsql:DbConnect",
          "dsql:DbConnectAdmin"
        ]
        Resource = aws_dsql_cluster.main.arn
      }
    ]
  })
}

# Attach to the caller identity (the dev profile user)
resource "aws_iam_user_policy_attachment" "dsql_attachment" {
  # We assume the caller is an IAM User for local dev. 
  # In a real setup with SSO or Roles, this needs adjustment to aws_iam_role_policy_attachment.
  # For simplicity, if we know the ARN is a user:
  count      = length(regexall("user/(.*)", data.aws_caller_identity.current.arn)) > 0 ? 1 : 0
  user       = regex("user/(.*)", data.aws_caller_identity.current.arn)[0]
  policy_arn = aws_iam_policy.dsql_access.arn
}
