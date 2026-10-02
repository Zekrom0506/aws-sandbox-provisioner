locals {
  account_id          = data.aws_caller_identity.current.account_id
  sandbox_bucket_arn  = "arn:aws:s3:::${var.sandbox_bucket_prefix}-*"
  sandbox_role_arn    = "arn:aws:iam::${local.account_id}:role${var.sandbox_role_path}*"
  provisioner_fn_name = "${var.project_name}-provisioner"
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------- Permissions boundary for every sandbox role ----------
# Even if the inline policy on a sandbox role were changed, the role can never
# do more than this boundary allows.

data "aws_iam_policy_document" "sandbox_boundary" {
  statement {
    sid       = "OnlySandboxBuckets"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [local.sandbox_bucket_arn, "${local.sandbox_bucket_arn}/*"]
  }
}

resource "aws_iam_policy" "sandbox_boundary" {
  name        = "${var.project_name}-sandbox-boundary"
  description = "Upper limit of permissions for sandbox roles"
  policy      = data.aws_iam_policy_document.sandbox_boundary.json
}

# ---------- Slack handler Lambdas (slash command + button clicks) ----------

resource "aws_iam_role" "slack_handlers" {
  name               = "${var.project_name}-slack-handlers"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "slack_handlers" {
  statement {
    sid       = "RequestTable"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.sandbox_requests.arn]
  }

  statement {
    sid       = "StartProvisioner"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${var.aws_region}:${local.account_id}:function:${local.provisioner_fn_name}"]
  }
}

resource "aws_iam_role_policy" "slack_handlers" {
  name   = "slack-handlers"
  role   = aws_iam_role.slack_handlers.id
  policy = data.aws_iam_policy_document.slack_handlers.json
}

resource "aws_iam_role_policy_attachment" "slack_handlers_logs" {
  role       = aws_iam_role.slack_handlers.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------- Provisioner Lambda ----------

resource "aws_iam_role" "provisioner" {
  name               = "${var.project_name}-provisioner"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "provisioner" {
  statement {
    sid       = "RequestTable"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.sandbox_requests.arn]
  }

  statement {
    sid = "CreateSandboxBuckets"
    actions = [
      "s3:CreateBucket",
      "s3:PutBucketTagging",
      "s3:PutBucketPublicAccessBlock",
    ]
    resources = [local.sandbox_bucket_arn]
  }

  statement {
    sid       = "CreateSandboxRolesOnlyWithBoundary"
    actions   = ["iam:CreateRole", "iam:PutRolePolicy"]
    resources = [local.sandbox_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.sandbox_boundary.arn]
    }
  }

  statement {
    sid       = "TagSandboxRoles"
    actions   = ["iam:TagRole"]
    resources = [local.sandbox_role_arn]
  }
}

resource "aws_iam_role_policy" "provisioner" {
  name   = "provisioner"
  role   = aws_iam_role.provisioner.id
  policy = data.aws_iam_policy_document.provisioner.json
}

resource "aws_iam_role_policy_attachment" "provisioner_logs" {
  role       = aws_iam_role.provisioner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------- Cleanup Lambda ----------

resource "aws_iam_role" "cleanup" {
  name               = "${var.project_name}-cleanup"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "cleanup" {
  statement {
    sid       = "RequestTable"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.sandbox_requests.arn]
  }

  statement {
    sid       = "ListBuckets"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  statement {
    sid = "DeleteSandboxBuckets"
    actions = [
      "s3:GetBucketTagging",
      "s3:ListBucket",
      "s3:ListBucketVersions",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:DeleteBucket",
    ]
    resources = [local.sandbox_bucket_arn, "${local.sandbox_bucket_arn}/*"]
  }

  statement {
    sid       = "ListRoles"
    actions   = ["iam:ListRoles"]
    resources = ["*"]
  }

  statement {
    sid = "DeleteSandboxRoles"
    actions = [
      "iam:ListRoleTags",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:DeleteRole",
    ]
    resources = [local.sandbox_role_arn]
  }
}

resource "aws_iam_role_policy" "cleanup" {
  name   = "cleanup"
  role   = aws_iam_role.cleanup.id
  policy = data.aws_iam_policy_document.cleanup.json
}

resource "aws_iam_role_policy_attachment" "cleanup_logs" {
  role       = aws_iam_role.cleanup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
