output "slash_command_url" {
  description = "Paste this as the Request URL of the /sandbox slash command"
  value       = "${aws_apigatewayv2_api.slack.api_endpoint}/slack/commands"
}

output "interactivity_url" {
  description = "Paste this as the Interactivity Request URL in the Slack app"
  value       = "${aws_apigatewayv2_api.slack.api_endpoint}/slack/interactions"
}

output "requests_table_name" {
  value = aws_dynamodb_table.sandbox_requests.name
}

output "sandbox_boundary_policy_arn" {
  value = aws_iam_policy.sandbox_boundary.arn
}
