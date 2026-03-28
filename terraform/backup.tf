resource "aws_iam_role" "backup_role" {
  name = "${var.project}-${var.env}-backup-role"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": ["sts:AssumeRole"],
      "Effect": "allow",
      "Principal": {
        "Service": ["backup.amazonaws.com"]
      }
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "backup_attachment" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
  role       = aws_iam_role.backup_role.name
}

resource "aws_backup_vault" "main" {
  name = "${var.project}-${var.env}-vault"
}

resource "aws_backup_plan" "daily" {
  name = "${var.project}-${var.env}-daily-backup"

  rule {
    rule_name         = "daily-backup-rule"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 17 * * ? *)" # 17:00 UTC -> 02:00 JST

    lifecycle {
      delete_after = 7 # 7 days retention
    }
  }
}

resource "aws_backup_selection" "dsql_selection" {
  iam_role_arn = aws_iam_role.backup_role.arn
  name         = "${var.project}-${var.env}-dsql-selection"
  plan_id      = aws_backup_plan.daily.id

  resources = [
    aws_dsql_cluster.main.arn
  ]
}
