"""
End-to-end expiry test: request a one-minute sandbox, let it expire,
run the scheduled cleanup and check that no tagged resources are left.

By default this runs against moto. Set RUN_AWS_TESTS=1 (with real AWS
credentials and REQUESTS_TABLE_NAME pointing at the deployed table) to
run the same flow against a real account; that version really waits a minute.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import boto3
import pytest

from conftest import MANAGER_ID, REQUESTER_ID
from handlers import cleanup as cleanup_handler
from handlers import provisioner as provisioner_handler
from helpers import find_resources_tagged_with_request
from sandbox import request_store

ONE_MINUTE = 1


def request_and_provision_one_minute_sandbox():
    request_item = request_store.create_request(REQUESTER_ID, "expiry-test", ONE_MINUTE, "expiry test")
    request_id = request_item["request_id"]
    request_store.mark_pending_request_decided(request_id, request_store.STATUS_APPROVED, MANAGER_ID)

    result = provisioner_handler.lambda_handler({"request_id": request_id}, None)
    assert result["status"] == "ACTIVE"
    return request_id


def test_one_minute_sandbox_is_fully_removed(aws, sent_slack_messages, monkeypatch):
    request_id = request_and_provision_one_minute_sandbox()

    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")
    assert len(find_resources_tagged_with_request(s3_client, iam_client, request_id)) == 2

    # Cleanup before expiry must not delete anything.
    cleanup_handler.lambda_handler({}, None)
    assert len(find_resources_tagged_with_request(s3_client, iam_client, request_id)) == 2

    two_minutes_later = datetime.now(timezone.utc) + timedelta(minutes=2)
    monkeypatch.setattr(cleanup_handler, "get_current_time", lambda: two_minutes_later)

    result = cleanup_handler.lambda_handler({}, None)

    assert request_id in result["deleted_request_ids"]
    assert find_resources_tagged_with_request(s3_client, iam_client, request_id) == []
    assert request_store.get_request(request_id)["status"] == "EXPIRED"


@pytest.mark.aws
@pytest.mark.skipif(os.environ.get("RUN_AWS_TESTS") != "1", reason="set RUN_AWS_TESTS=1 to run against real AWS")
def test_one_minute_sandbox_is_fully_removed_in_real_aws(sent_slack_messages):
    request_id = request_and_provision_one_minute_sandbox()

    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")
    assert len(find_resources_tagged_with_request(s3_client, iam_client, request_id)) == 2

    time.sleep(65)
    cleanup_handler.lambda_handler({}, None)

    assert find_resources_tagged_with_request(s3_client, iam_client, request_id) == []
    assert request_store.get_request(request_id)["status"] == "EXPIRED"
