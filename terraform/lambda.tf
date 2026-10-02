data "archive_file" "lambda_code" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/lambda.zip"
  excludes    = ["**/__pycache__/**"]
}

locals {
  common_environment = {
    REQUESTS_TABLE_NAME   = aws_dynamodb_table.sandbox_requests.name
    SANDBOX_BUCKET_PREFIX = var.sandbox_bucket_prefix
    SANDBOX_ROLE_PATH     = var.sandbox_role_path
    SLACK_BOT_TOKEN       = var.slack_bot_token
  }
}

resource "aws_lambda_function" "slash_command" {
  function_name    = "${var.project_name}-slash-command"
  role             = aws_iam_role.slack_handlers.arn
  runtime          = "python3.12"
  handler          = "handlers.slash_command.lambda_handler"
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256
  timeout          = 10

  environment {
    variables = merge(local.common_environment, {
      SLACK_SIGNING_SECRET      = var.slack_signing_secret
      SLACK_APPROVAL_CHANNEL_ID = var.slack_approval_channel_id
      DEFAULT_DURATION_HOURS    = tostring(var.default_duration_hours)
      MAX_DURATION_HOURS        = tostring(var.max_duration_hours)
    })
  }
}

resource "aws_lambda_function" "interactivity" {
  function_name    = "${var.project_name}-interactivity"
  role             = aws_iam_role.slack_handlers.arn
  runtime          = "python3.12"
  handler          = "handlers.interactivity.lambda_handler"
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256
  timeout          = 10

  environment {
    variables = merge(local.common_environment, {
      SLACK_SIGNING_SECRET      = var.slack_signing_secret
      MANAGER_SLACK_IDS         = join(",", var.manager_slack_ids)
      PROVISIONER_FUNCTION_NAME = local.provisioner_fn_name
    })
  }
}

resource "aws_lambda_function" "provisioner" {
  function_name    = local.provisioner_fn_name
  role             = aws_iam_role.provisioner.arn
  runtime          = "python3.12"
  handler          = "handlers.provisioner.lambda_handler"
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256
  timeout          = 60

  environment {
    variables = merge(local.common_environment, {
      SANDBOX_PERMISSIONS_BOUNDARY_ARN = aws_iam_policy.sandbox_boundary.arn
    })
  }
}

resource "aws_lambda_function" "cleanup" {
  function_name    = "${var.project_name}-cleanup"
  role             = aws_iam_role.cleanup.arn
  runtime          = "python3.12"
  handler          = "handlers.cleanup.lambda_handler"
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256
  timeout          = 300

  environment {
    variables = local.common_environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset([
    aws_lambda_function.slash_command.function_name,
    aws_lambda_function.interactivity.function_name,
    aws_lambda_function.provisioner.function_name,
    aws_lambda_function.cleanup.function_name,
  ])

  name              = "/aws/lambda/${each.value}"
  retention_in_days = var.log_retention_days
}
