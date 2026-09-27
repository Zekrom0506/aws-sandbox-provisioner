import boto3

from conftest import REQUESTER_ID
from handlers import provisioner as provisioner_handler
from sandbox import provisioner, request_store
from sandbox.tags import aws_list_to_tags


def test_create_sandbox_creates_tagged_bucket_and_role(aws):
    sandbox = provisioner.create_sandbox("a1b2c3d4e5f6", "utkarsh", REQUESTER_ID, duration_minutes=60)

    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")

    bucket_tags = aws_list_to_tags(s3_client.get_bucket_tagging(Bucket=sandbox["bucket_name"])["TagSet"])
    assert bucket_tags["Owner"] == "utkarsh"
    assert bucket_tags["RequestId"] == "a1b2c3d4e5f6"
    assert bucket_tags["ExpiresAt"] == sandbox["expires_at"]

    role = iam_client.get_role(RoleName=sandbox["role_name"])["Role"]
    assert role["Path"] == "/sandbox/"
    role_tags = aws_list_to_tags(iam_client.list_role_tags(RoleName=sandbox["role_name"])["Tags"])
    assert role_tags["Owner"] == "utkarsh"
    assert role_tags["ExpiresAt"] == sandbox["expires_at"]


def test_role_policy_only_allows_its_own_bucket(aws):
    sandbox = provisioner.create_sandbox("a1b2c3d4e5f6", "utkarsh", REQUESTER_ID, duration_minutes=60)

    iam_client = boto3.client("iam")
    policy = iam_client.get_role_policy(RoleName=sandbox["role_name"], PolicyName="sandbox-bucket-access")
    statements = policy["PolicyDocument"]["Statement"]

    for statement in statements:
        assert sandbox["bucket_name"] in statement["Resource"]
        for action in statement["Action"]:
            assert action.startswith("s3:")
            assert action != "s3:*"


def test_bucket_blocks_public_access(aws):
    sandbox = provisioner.create_sandbox("a1b2c3d4e5f6", "utkarsh", REQUESTER_ID, duration_minutes=60)

    s3_client = boto3.client("s3")
    settings = s3_client.get_public_access_block(Bucket=sandbox["bucket_name"])["PublicAccessBlockConfiguration"]

    assert settings["BlockPublicAcls"] is True
    assert settings["RestrictPublicBuckets"] is True


def test_handler_marks_request_active(aws, sent_slack_messages):
    request_item = request_store.create_request(REQUESTER_ID, "utkarsh", 120, "testing")
    request_id = request_item["request_id"]
    request_store.update_request(request_id, request_store.STATUS_APPROVED)

    result = provisioner_handler.lambda_handler({"request_id": request_id}, None)

    saved = request_store.get_request(request_id)
    assert result["status"] == "ACTIVE"
    assert saved["status"] == "ACTIVE"
    assert saved["bucket_name"] == result["sandbox"]["bucket_name"]
    assert saved["expires_at"] == result["sandbox"]["expires_at"]
    assert sent_slack_messages[0]["channel"] == REQUESTER_ID
    assert "is ready" in sent_slack_messages[0]["text"]


def test_handler_skips_requests_that_are_not_approved(aws, sent_slack_messages):
    request_item = request_store.create_request(REQUESTER_ID, "utkarsh", 120, "testing")

    result = provisioner_handler.lambda_handler({"request_id": request_item["request_id"]}, None)

    assert result["status"] == "PENDING"
    assert boto3.client("s3").list_buckets()["Buckets"] == []
