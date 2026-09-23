from datetime import datetime, timedelta, timezone

from sandbox import tags


def test_build_sandbox_tags_contains_owner_and_expiry():
    expires_at = datetime(2026, 9, 20, 10, 30, 0, tzinfo=timezone.utc)

    result = tags.build_sandbox_tags("abc123", "utkarsh", "U123", expires_at)

    assert result["Owner"] == "utkarsh"
    assert result["OwnerSlackId"] == "U123"
    assert result["ExpiresAt"] == "2026-09-20T10:30:00Z"
    assert result["RequestId"] == "abc123"
    assert result["ManagedBy"] == "sandbox-provisioner"


def test_time_format_round_trip():
    moment = datetime(2026, 9, 20, 10, 30, 0, tzinfo=timezone.utc)

    assert tags.parse_time(tags.format_time(moment)) == moment


def test_is_expired():
    now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    past_tags = {"ExpiresAt": tags.format_time(now - timedelta(minutes=1))}
    future_tags = {"ExpiresAt": tags.format_time(now + timedelta(minutes=1))}

    assert tags.is_expired(past_tags, now) is True
    assert tags.is_expired(future_tags, now) is False
    assert tags.is_expired({}, now) is False


def test_aws_list_conversion():
    original = {"Owner": "utkarsh", "RequestId": "abc"}

    assert tags.aws_list_to_tags(tags.tags_to_aws_list(original)) == original
