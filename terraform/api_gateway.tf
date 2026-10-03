resource "aws_apigatewayv2_api" "slack" {
  name          = "${var.project_name}-slack-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.slack.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "slash_command" {
  api_id                 = aws_apigatewayv2_api.slack.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.slash_command.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "interactivity" {
  api_id                 = aws_apigatewayv2_api.slack.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.interactivity.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "slash_command" {
  api_id    = aws_apigatewayv2_api.slack.id
  route_key = "POST /slack/commands"
  target    = "integrations/${aws_apigatewayv2_integration.slash_command.id}"
}

resource "aws_apigatewayv2_route" "interactivity" {
  api_id    = aws_apigatewayv2_api.slack.id
  route_key = "POST /slack/interactions"
  target    = "integrations/${aws_apigatewayv2_integration.interactivity.id}"
}

resource "aws_lambda_permission" "api_invoke_slash_command" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slash_command.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.slack.execution_arn}/*/*"
}

resource "aws_lambda_permission" "api_invoke_interactivity" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.interactivity.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.slack.execution_arn}/*/*"
}
