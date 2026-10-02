variable "aws_region" {
  description = "Region where the provisioner and the sandboxes live"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix used for every resource name"
  type        = string
  default     = "sandbox-provisioner"
}

variable "sandbox_bucket_prefix" {
  description = "Every sandbox bucket name starts with this prefix"
  type        = string
  default     = "sandbox"
}

variable "sandbox_role_path" {
  description = "IAM path for sandbox roles, used to keep their permissions separate"
  type        = string
  default     = "/sandbox/"
}

variable "slack_signing_secret" {
  description = "Signing secret from the Slack app's Basic Information page"
  type        = string
  sensitive   = true
}

variable "slack_bot_token" {
  description = "Bot token (xoxb-...) with the chat:write scope"
  type        = string
  sensitive   = true
}

variable "slack_approval_channel_id" {
  description = "Channel where managers see the Approve / Deny buttons"
  type        = string
}

variable "manager_slack_ids" {
  description = "Slack user IDs that are allowed to approve sandboxes"
  type        = list(string)
}

variable "default_duration_hours" {
  description = "Used when the user does not pass a duration to /sandbox"
  type        = number
  default     = 4
}

variable "max_duration_hours" {
  description = "Longest sandbox a user can ask for"
  type        = number
  default     = 24
}

variable "cleanup_schedule" {
  description = "How often EventBridge runs the cleanup Lambda"
  type        = string
  default     = "rate(5 minutes)"
}

variable "log_retention_days" {
  description = "How long Lambda logs are kept in CloudWatch"
  type        = number
  default     = 14
}
