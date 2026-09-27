import json
from datetime import datetime, timedelta, timezone

import boto3

from sandbox import config
from sandbox.tags import build_sandbox_tags, tags_to_aws_list


def get_account_id(sts_client):
    identity = sts_client.get_caller_identity()
    return identity["Account"]


def build_bucket_name(request_id, account_id):
    short_id = request_id[:8]
    return f"{config.get_bucket_prefix()}-{short_id}-{account_id}".lower()


def build_role_name(request_id):
    short_id = request_id[:8]
    return f"sandbox-{short_id}-role"


def build_trust_policy(account_id):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                "Action": "sts:AssumeRole",
            }
        ],
    }


def build_bucket_access_policy(bucket_name):
    """The sandbox role can only touch its own bucket and nothing else."""
    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ListOwnBucket",
                "Effect": "Allow",
                "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                "Resource": bucket_arn,
            },
            {
                "Sid": "ReadWriteOwnObjects",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                "Resource": f"{bucket_arn}/*",
            },
        ],
    }


def create_bucket(s3_client, bucket_name, tags):
    region = s3_client.meta.region_name
    if region == "us-east-1":
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region},
        )

    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3_client.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": tags_to_aws_list(tags)})


def create_role(iam_client, role_name, account_id, bucket_name, tags):
    create_role_arguments = {
        "RoleName": role_name,
        "Path": config.get_role_path(),
        "AssumeRolePolicyDocument": json.dumps(build_trust_policy(account_id)),
        "Description": f"Temporary sandbox role for bucket {bucket_name}",
        "MaxSessionDuration": 3600,
        "Tags": tags_to_aws_list(tags),
    }

    boundary_arn = config.get_permissions_boundary_arn()
    if boundary_arn != "":
        create_role_arguments["PermissionsBoundary"] = boundary_arn

    response = iam_client.create_role(**create_role_arguments)

    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="sandbox-bucket-access",
        PolicyDocument=json.dumps(build_bucket_access_policy(bucket_name)),
    )
    return response["Role"]["Arn"]


def create_sandbox(request_id, owner_name, owner_slack_id, duration_minutes, now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")
    sts_client = boto3.client("sts")

    account_id = get_account_id(sts_client)
    expires_at = now + timedelta(minutes=int(duration_minutes))
    tags = build_sandbox_tags(request_id, owner_name, owner_slack_id, expires_at)

    bucket_name = build_bucket_name(request_id, account_id)
    role_name = build_role_name(request_id)

    create_bucket(s3_client, bucket_name, tags)
    role_arn = create_role(iam_client, role_name, account_id, bucket_name, tags)

    return {
        "bucket_name": bucket_name,
        "role_name": role_name,
        "role_arn": role_arn,
        "expires_at": tags["ExpiresAt"],
    }
