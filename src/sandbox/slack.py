import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request

from sandbox import config

SLACK_API_URL = "https://slack.com/api/"
MAX_REQUEST_AGE_SECONDS = 60 * 5


def get_raw_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return body


def get_header(event, header_name):
    headers = event.get("headers") or {}
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return value
    return None


def is_valid_signature(event, signing_secret, current_time=None):
    """Checks the X-Slack-Signature header as described in Slack's request verification docs."""
    if current_time is None:
        current_time = time.time()

    timestamp = get_header(event, "X-Slack-Request-Timestamp")
    received_signature = get_header(event, "X-Slack-Signature")
    if timestamp is None or received_signature is None:
        return False

    # Old timestamps are rejected so a captured request cannot be replayed later.
    if abs(current_time - int(timestamp)) > MAX_REQUEST_AGE_SECONDS:
        return False

    base_string = f"v0:{timestamp}:{get_raw_body(event)}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected_signature = f"v0={digest}"

    return hmac.compare_digest(expected_signature, received_signature)


def parse_form_body(event):
    parsed = urllib.parse.parse_qs(get_raw_body(event))
    form = {}
    for key, values in parsed.items():
        form[key] = values[0]
    return form


def call_slack_api(method_name, payload):
    request = urllib.request.Request(
        SLACK_API_URL + method_name,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {config.get_slack_bot_token()}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response_data = json.loads(response.read().decode("utf-8"))

    if not response_data.get("ok"):
        raise RuntimeError(f"Slack API {method_name} failed: {response_data.get('error')}")
    return response_data


def post_message(channel_id, text, blocks=None):
    payload = {"channel": channel_id, "text": text}
    if blocks is not None:
        payload["blocks"] = blocks
    return call_slack_api("chat.postMessage", payload)


def post_to_response_url(response_url, payload):
    request = urllib.request.Request(
        response_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def build_http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def build_approval_blocks(request_item):
    request_id = request_item["request_id"]
    duration_hours = int(request_item["duration_minutes"]) / 60
    summary_text = (
        f"*New sandbox request* from <@{request_item['requester_id']}>\n"
        f"*Duration:* {duration_hours:g} hour(s)\n"
        f"*Reason:* {request_item['reason']}\n"
        f"*Request ID:* `{request_id}`"
    )

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}},
        {
            "type": "actions",
            "block_id": "sandbox_decision",
            "elements": [
                {
                    "type": "button",
                    "action_id": "approve_sandbox",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "value": request_id,
                },
                {
                    "type": "button",
                    "action_id": "deny_sandbox",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "value": request_id,
                },
            ],
        },
    ]
