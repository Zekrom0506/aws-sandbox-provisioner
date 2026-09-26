import logging

from sandbox import config, request_store, slack

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USAGE_TEXT = "Usage: `/sandbox <hours> <reason>`  for example `/sandbox 4 testing S3 lifecycle rules`"


def parse_command_text(text):
    """Turns '/sandbox 4 testing lifecycle rules' text into (hours, reason)."""
    words = text.strip().split()
    hours = config.get_default_duration_hours()
    reason_words = words

    if len(words) > 0 and words[0].isdigit():
        hours = int(words[0])
        reason_words = words[1:]

    reason = " ".join(reason_words)
    if reason == "":
        reason = "No reason given"
    return hours, reason


def build_ephemeral_reply(text):
    return slack.build_http_response(200, {"response_type": "ephemeral", "text": text})


def lambda_handler(event, context):
    if not slack.is_valid_signature(event, config.get_slack_signing_secret()):
        logger.warning("Rejected request with an invalid Slack signature")
        return slack.build_http_response(401, {"error": "invalid signature"})

    form = slack.parse_form_body(event)
    command_text = form.get("text", "")

    if command_text.strip().lower() == "help":
        return build_ephemeral_reply(USAGE_TEXT)

    hours, reason = parse_command_text(command_text)
    max_hours = config.get_max_duration_hours()
    if hours < 1 or hours > max_hours:
        return build_ephemeral_reply(f"Duration must be between 1 and {max_hours} hours. {USAGE_TEXT}")

    request_item = request_store.create_request(
        requester_id=form["user_id"],
        requester_name=form.get("user_name", form["user_id"]),
        duration_minutes=hours * 60,
        reason=reason,
    )
    logger.info("Created sandbox request %s for %s", request_item["request_id"], form["user_id"])

    slack.post_message(
        config.get_approval_channel_id(),
        text=f"Sandbox request from <@{form['user_id']}> is waiting for approval",
        blocks=slack.build_approval_blocks(request_item),
    )

    return build_ephemeral_reply(
        f"Your sandbox request `{request_item['request_id']}` for {hours} hour(s) was sent to a manager for approval."
    )
