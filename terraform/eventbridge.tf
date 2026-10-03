resource "aws_cloudwatch_event_rule" "cleanup_schedule" {
  name                = "${var.project_name}-cleanup"
  description         = "Deletes sandboxes whose ExpiresAt tag is in the past"
  schedule_expression = var.cleanup_schedule
}

resource "aws_cloudwatch_event_target" "cleanup_lambda" {
  rule = aws_cloudwatch_event_rule.cleanup_schedule.name
  arn  = aws_lambda_function.cleanup.arn
}

resource "aws_lambda_permission" "eventbridge_invoke_cleanup" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cleanup_schedule.arn
}
