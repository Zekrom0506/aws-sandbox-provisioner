import hashlib
import hmac
import json
import time
import urllib.parse

from conftest import TEST_SIGNING_SECRET


def build_signed_event(form_fields, timestamp=None, secret=TEST_SIGNING_SECRET):
    if timestamp is None:
        timestamp = int(time.time())

    body = urllib.parse.urlencode(form_fields)
    base_string = f"v0:{timestamp}:{body}"
    signature = "v0=" + hmac.new(secret.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    return {
        "body": body,
        "isBase64Encoded": False,
        "headers": {
            "x-slack-request-timestamp": str(timestamp),
            "x-slack-signature": signature,
        },
    }


def build_button_click_event(action_id, request_id, clicked_by):
    payload = {
        "type": "block_actions",
        "user": {"id": clicked_by},
        "response_url": "https://hooks.slack.com/actions/test",
        "actions": [{"action_id": action_id, "value": request_id}],
    }
    return build_signed_event({"payload": json.dumps(payload)})


def find_resources_tagged_with_request(s3_client, iam_client, request_id):
    """Looks at every S3 bucket and sandbox IAM role and returns the ones tagged with this request id."""
    remaining = []

    for bucket in s3_client.list_buckets().get("Buckets", []):
        try:
            tag_set = s3_client.get_bucket_tagging(Bucket=bucket["Name"])["TagSet"]
        except Exception:
            continue
        for tag in tag_set:
            if tag["Key"] == "RequestId" and tag["Value"] == request_id:
                remaining.append("bucket:" + bucket["Name"])

    for role in iam_client.list_roles(PathPrefix="/sandbox/")["Roles"]:
        tags = iam_client.list_role_tags(RoleName=role["RoleName"])["Tags"]
        for tag in tags:
            if tag["Key"] == "RequestId" and tag["Value"] == request_id:
                remaining.append("role:" + role["RoleName"])

    return remaining
