import base64
import time

from conftest import TEST_SIGNING_SECRET
from helpers import build_signed_event
from sandbox import slack


def test_valid_signature_is_accepted():
    event = build_signed_event({"command": "/sandbox", "text": "2 testing"})

    assert slack.is_valid_signature(event, TEST_SIGNING_SECRET) is True


def test_wrong_secret_is_rejected():
    event = build_signed_event({"command": "/sandbox"}, secret="someone-else")

    assert slack.is_valid_signature(event, TEST_SIGNING_SECRET) is False


def test_old_request_is_rejected():
    ten_minutes_ago = int(time.time()) - 600
    event = build_signed_event({"command": "/sandbox"}, timestamp=ten_minutes_ago)

    assert slack.is_valid_signature(event, TEST_SIGNING_SECRET) is False


def test_missing_headers_are_rejected():
    event = {"body": "command=%2Fsandbox", "headers": {}}

    assert slack.is_valid_signature(event, TEST_SIGNING_SECRET) is False


def test_base64_body_is_decoded():
    event = build_signed_event({"text": "hello world"})
    event["body"] = base64.b64encode(event["body"].encode()).decode()
    event["isBase64Encoded"] = True

    assert slack.is_valid_signature(event, TEST_SIGNING_SECRET) is True
    assert slack.parse_form_body(event)["text"] == "hello world"


def test_approval_blocks_have_two_buttons():
    request_item = {
        "request_id": "req123",
        "requester_id": "U1",
        "duration_minutes": 120,
        "reason": "load testing",
    }

    blocks = slack.build_approval_blocks(request_item)
    buttons = blocks[1]["elements"]

    assert buttons[0]["action_id"] == "approve_sandbox"
    assert buttons[1]["action_id"] == "deny_sandbox"
    assert buttons[0]["value"] == "req123"
    assert "2 hour(s)" in blocks[0]["text"]["text"]
