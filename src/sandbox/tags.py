from datetime import datetime, timezone

MANAGED_BY_KEY = "ManagedBy"
MANAGED_BY_VALUE = "sandbox-provisioner"
OWNER_KEY = "Owner"
OWNER_SLACK_ID_KEY = "OwnerSlackId"
EXPIRES_AT_KEY = "ExpiresAt"
REQUEST_ID_KEY = "RequestId"


def format_time(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text):
    parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=timezone.utc)


def build_sandbox_tags(request_id, owner_name, owner_slack_id, expires_at):
    return {
        MANAGED_BY_KEY: MANAGED_BY_VALUE,
        OWNER_KEY: owner_name,
        OWNER_SLACK_ID_KEY: owner_slack_id,
        EXPIRES_AT_KEY: format_time(expires_at),
        REQUEST_ID_KEY: request_id,
    }


def tags_to_aws_list(tags):
    tag_list = []
    for key, value in tags.items():
        tag_list.append({"Key": key, "Value": value})
    return tag_list


def aws_list_to_tags(tag_list):
    tags = {}
    for tag in tag_list:
        tags[tag["Key"]] = tag["Value"]
    return tags


def is_managed_sandbox(tags):
    return tags.get(MANAGED_BY_KEY) == MANAGED_BY_VALUE


def is_expired(tags, now):
    expires_at_text = tags.get(EXPIRES_AT_KEY)
    if expires_at_text is None:
        return False
    expires_at = parse_time(expires_at_text)
    return expires_at <= now
