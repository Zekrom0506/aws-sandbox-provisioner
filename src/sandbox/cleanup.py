import logging

from botocore.exceptions import ClientError

from sandbox import config
from sandbox.tags import aws_list_to_tags, is_expired, is_managed_sandbox

logger = logging.getLogger(__name__)


def get_bucket_tags(s3_client, bucket_name):
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        return aws_list_to_tags(response["TagSet"])
    except ClientError as error:
        error_code = error.response["Error"]["Code"]
        if error_code in ("NoSuchTagSet", "NoSuchBucket", "AccessDenied"):
            return {}
        raise


def find_sandbox_buckets(s3_client):
    sandbox_buckets = []
    prefix = config.get_bucket_prefix() + "-"
    response = s3_client.list_buckets()
    for bucket in response.get("Buckets", []):
        bucket_name = bucket["Name"]
        if not bucket_name.startswith(prefix):
            continue
        tags = get_bucket_tags(s3_client, bucket_name)
        if is_managed_sandbox(tags):
            sandbox_buckets.append({"name": bucket_name, "tags": tags})
    return sandbox_buckets


def find_sandbox_roles(iam_client):
    sandbox_roles = []
    paginator = iam_client.get_paginator("list_roles")
    for page in paginator.paginate(PathPrefix=config.get_role_path()):
        for role in page["Roles"]:
            role_name = role["RoleName"]
            tag_response = iam_client.list_role_tags(RoleName=role_name)
            tags = aws_list_to_tags(tag_response["Tags"])
            if is_managed_sandbox(tags):
                sandbox_roles.append({"name": role_name, "tags": tags})
    return sandbox_roles


def empty_bucket(s3_client, bucket_name):
    paginator = s3_client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket_name):
        objects_to_delete = []
        for version in page.get("Versions", []):
            objects_to_delete.append({"Key": version["Key"], "VersionId": version["VersionId"]})
        for marker in page.get("DeleteMarkers", []):
            objects_to_delete.append({"Key": marker["Key"], "VersionId": marker["VersionId"]})

        if len(objects_to_delete) > 0:
            s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})


def delete_bucket(s3_client, bucket_name):
    empty_bucket(s3_client, bucket_name)
    s3_client.delete_bucket(Bucket=bucket_name)


def delete_role(iam_client, role_name):
    # IAM refuses to delete a role that still has policies on it.
    inline_policies = iam_client.list_role_policies(RoleName=role_name)
    for policy_name in inline_policies["PolicyNames"]:
        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in attached_policies["AttachedPolicies"]:
        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    iam_client.delete_role(RoleName=role_name)


def delete_expired_sandboxes(s3_client, iam_client, now):
    """Deletes every expired sandbox resource and returns the request ids that were cleaned up."""
    cleaned_request_ids = set()

    for bucket in find_sandbox_buckets(s3_client):
        if is_expired(bucket["tags"], now):
            logger.info("Deleting expired bucket %s", bucket["name"])
            delete_bucket(s3_client, bucket["name"])
            cleaned_request_ids.add(bucket["tags"].get("RequestId"))

    for role in find_sandbox_roles(iam_client):
        if is_expired(role["tags"], now):
            logger.info("Deleting expired role %s", role["name"])
            delete_role(iam_client, role["name"])
            cleaned_request_ids.add(role["tags"].get("RequestId"))

    cleaned_request_ids.discard(None)
    return sorted(cleaned_request_ids)
