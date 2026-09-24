import os


def get_setting(name, default_value=None):
    value = os.environ.get(name, default_value)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_table_name():
    return get_setting("REQUESTS_TABLE_NAME", "sandbox-requests")


def get_bucket_prefix():
    return get_setting("SANDBOX_BUCKET_PREFIX", "sandbox")


def get_role_path():
    return get_setting("SANDBOX_ROLE_PATH", "/sandbox/")


def get_permissions_boundary_arn():
    return os.environ.get("SANDBOX_PERMISSIONS_BOUNDARY_ARN", "")


def get_slack_signing_secret():
    return get_setting("SLACK_SIGNING_SECRET")


def get_slack_bot_token():
    return get_setting("SLACK_BOT_TOKEN")


def get_approval_channel_id():
    return get_setting("SLACK_APPROVAL_CHANNEL_ID")


def get_manager_slack_ids():
    raw_value = get_setting("MANAGER_SLACK_IDS", "")
    manager_ids = []
    for item in raw_value.split(","):
        cleaned_item = item.strip()
        if cleaned_item != "":
            manager_ids.append(cleaned_item)
    return manager_ids


def get_provisioner_function_name():
    return get_setting("PROVISIONER_FUNCTION_NAME")


def get_default_duration_hours():
    return int(get_setting("DEFAULT_DURATION_HOURS", "4"))


def get_max_duration_hours():
    return int(get_setting("MAX_DURATION_HOURS", "24"))
