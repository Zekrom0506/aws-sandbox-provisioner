import json

from conftest import REQUESTER_ID
from handlers import slash_command
from helpers import build_signed_event
from sandbox import request_store


def build_command_event(text):
    return build_signed_event({
        "command": "/sandbox",
        "text": text,
        "user_id": REQUESTER_ID,
        "user_name": "utkarsh",
    })


def test_parse_command_text_with_hours_and_reason():
    assert slash_command.parse_command_text("6 testing glue jobs") == (6, "testing glue jobs")


def test_parse_command_text_uses_default_hours():
    assert slash_command.parse_command_text("just exploring") == (4, "just exploring")
    assert slash_command.parse_command_text("") == (4, "No reason given")


def test_request_is_saved_and_sent_to_managers(aws, sent_slack_messages):
    response = slash_command.lambda_handler(build_command_event("2 trying out S3 events"), None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["response_type"] == "ephemeral"

    items = request_store.get_table().scan()["Items"]
    assert len(items) == 1
    assert items[0]["status"] == "PENDING"
    assert items[0]["duration_minutes"] == 120
    assert items[0]["requester_id"] == REQUESTER_ID
    assert items[0]["reason"] == "trying out S3 events"

    assert len(sent_slack_messages) == 1
    assert sent_slack_messages[0]["channel"] == "CAPPROVALS"


def test_too_long_duration_is_refused(aws, sent_slack_messages):
    response = slash_command.lambda_handler(build_command_event("100 forever"), None)

    assert "between 1 and 24 hours" in json.loads(response["body"])["text"]
    assert request_store.get_table().scan()["Items"] == []
    assert sent_slack_messages == []


def test_invalid_signature_returns_401(aws, sent_slack_messages):
    event = build_command_event("2 testing")
    event["headers"]["x-slack-signature"] = "v0=not-a-real-signature"

    response = slash_command.lambda_handler(event, None)

    assert response["statusCode"] == 401
