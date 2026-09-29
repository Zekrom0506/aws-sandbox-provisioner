import pytest

from conftest import MANAGER_ID, REQUESTER_ID
from handlers import interactivity
from helpers import build_button_click_event
from sandbox import request_store


@pytest.fixture
def started_provisioning(monkeypatch):
    started_ids = []
    monkeypatch.setattr(interactivity, "start_provisioning", lambda request_id: started_ids.append(request_id))
    return started_ids


@pytest.fixture
def pending_request(aws):
    return request_store.create_request(REQUESTER_ID, "utkarsh", 60, "testing")


def test_manager_approval_starts_provisioning(pending_request, sent_slack_messages, started_provisioning):
    request_id = pending_request["request_id"]
    event = build_button_click_event("approve_sandbox", request_id, MANAGER_ID)

    response = interactivity.lambda_handler(event, None)

    assert response["statusCode"] == 200
    saved = request_store.get_request(request_id)
    assert saved["status"] == "APPROVED"
    assert saved["decided_by"] == MANAGER_ID
    assert started_provisioning == [request_id]
    assert "approved" in sent_slack_messages[0]["payload"]["text"]


def test_manager_can_deny(pending_request, sent_slack_messages, started_provisioning):
    request_id = pending_request["request_id"]
    event = build_button_click_event("deny_sandbox", request_id, MANAGER_ID)

    interactivity.lambda_handler(event, None)

    assert request_store.get_request(request_id)["status"] == "DENIED"
    assert started_provisioning == []
    requester_messages = [message for message in sent_slack_messages if message.get("channel") == REQUESTER_ID]
    assert len(requester_messages) == 1


def test_non_manager_cannot_approve(pending_request, sent_slack_messages, started_provisioning):
    request_id = pending_request["request_id"]
    event = build_button_click_event("approve_sandbox", request_id, "URANDOMUSER")

    interactivity.lambda_handler(event, None)

    assert request_store.get_request(request_id)["status"] == "PENDING"
    assert started_provisioning == []
    assert "Only managers" in sent_slack_messages[0]["payload"]["text"]


def test_double_click_only_provisions_once(pending_request, sent_slack_messages, started_provisioning):
    request_id = pending_request["request_id"]
    event = build_button_click_event("approve_sandbox", request_id, MANAGER_ID)

    interactivity.lambda_handler(event, None)
    interactivity.lambda_handler(event, None)

    assert started_provisioning == [request_id]
