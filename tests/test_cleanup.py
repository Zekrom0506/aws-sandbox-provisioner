from datetime import datetime, timedelta, timezone

import boto3

from conftest import REQUESTER_ID
from sandbox import cleanup, provisioner


def test_only_expired_sandboxes_are_deleted(aws):
    now = datetime.now(timezone.utc)
    expired = provisioner.create_sandbox("expired00001", "utkarsh", REQUESTER_ID, 60, now=now - timedelta(hours=2))
    active = provisioner.create_sandbox("active000001", "utkarsh", REQUESTER_ID, 60, now=now)

    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")

    deleted_ids = cleanup.delete_expired_sandboxes(s3_client, iam_client, now)

    bucket_names = [bucket["Name"] for bucket in s3_client.list_buckets()["Buckets"]]
    role_names = [role["RoleName"] for role in iam_client.list_roles(PathPrefix="/sandbox/")["Roles"]]

    assert deleted_ids == ["expired00001"]
    assert expired["bucket_name"] not in bucket_names
    assert expired["role_name"] not in role_names
    assert active["bucket_name"] in bucket_names
    assert active["role_name"] in role_names


def test_bucket_with_objects_is_emptied_before_delete(aws):
    now = datetime.now(timezone.utc)
    sandbox = provisioner.create_sandbox("withfiles001", "utkarsh", REQUESTER_ID, 1, now=now - timedelta(minutes=5))

    s3_client = boto3.client("s3")
    s3_client.put_object(Bucket=sandbox["bucket_name"], Key="data/report.csv", Body=b"a,b\n1,2\n")
    s3_client.put_object(Bucket=sandbox["bucket_name"], Key="notes.txt", Body=b"hello")

    cleanup.delete_expired_sandboxes(s3_client, boto3.client("iam"), now)

    assert s3_client.list_buckets()["Buckets"] == []


def test_resources_not_managed_by_us_are_ignored(aws):
    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")
    s3_client.create_bucket(Bucket="sandbox-someone-else")
    s3_client.put_bucket_tagging(
        Bucket="sandbox-someone-else",
        Tagging={"TagSet": [{"Key": "ExpiresAt", "Value": "2020-01-01T00:00:00Z"}]},
    )
    s3_client.create_bucket(Bucket="company-data")

    deleted_ids = cleanup.delete_expired_sandboxes(s3_client, iam_client, datetime.now(timezone.utc))

    bucket_names = [bucket["Name"] for bucket in s3_client.list_buckets()["Buckets"]]
    assert deleted_ids == []
    assert "sandbox-someone-else" in bucket_names
    assert "company-data" in bucket_names
