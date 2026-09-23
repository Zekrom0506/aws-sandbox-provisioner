import os

import boto3
import pytest
from moto import mock_aws

TEST_SIGNING_SECRET = "test-signing-secret"
MANAGER_ID = "UMANAGER1"
REQUESTER_ID = "UREQUEST1"


@pytest.fixture(autouse=True)
def app_environment(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", TEST_SIGNING_SECRET)
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_APPROVAL_CHANNEL_ID", "CAPPROVALS")
    monkeypatch.setenv("MANAGER_SLACK_IDS", f"{MANAGER_ID}, UMANAGER2")
    monkeypatch.setenv("PROVISIONER_FUNCTION_NAME", "sandbox-provisioner")
    monkeypatch.setenv("SANDBOX_BUCKET_PREFIX", "sandbox")
    monkeypatch.setenv("SANDBOX_ROLE_PATH", "/sandbox/")

    # Real AWS tests bring their own credentials and table name.
    if os.environ.get("RUN_AWS_TESTS") != "1":
        monkeypatch.setenv("REQUESTS_TABLE_NAME", "sandbox-requests-test")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def aws():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="sandbox-requests-test",
            KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def sent_slack_messages(monkeypatch):
    """Captures Slack messages instead of calling the real Slack API."""
    from sandbox import slack

    messages = []

    def fake_post_message(channel_id, text, blocks=None):
        messages.append({"channel": channel_id, "text": text, "blocks": blocks})
        return {"ok": True}

    def fake_post_to_response_url(response_url, payload):
        messages.append({"response_url": response_url, "payload": payload})
        return 200

    monkeypatch.setattr(slack, "post_message", fake_post_message)
    monkeypatch.setattr(slack, "post_to_response_url", fake_post_to_response_url)
    return messages
