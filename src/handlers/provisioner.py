import logging

from sandbox import provisioner, request_store, slack

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def build_ready_message(request_id, sandbox):
    return (
        f"Your sandbox `{request_id}` is ready.\n"
        f"*S3 bucket:* `{sandbox['bucket_name']}`\n"
        f"*IAM role:* `{sandbox['role_arn']}`\n"
        f"*Expires at:* {sandbox['expires_at']} (UTC). Everything will be deleted automatically after that."
    )


def lambda_handler(event, context):
    request_id = event["request_id"]
    request_item = request_store.get_request(request_id)

    if request_item is None:
        logger.error("Request %s was not found", request_id)
        return {"status": "NOT_FOUND"}

    if request_item["status"] != request_store.STATUS_APPROVED:
        logger.warning("Request %s has status %s, skipping", request_id, request_item["status"])
        return {"status": request_item["status"]}

    requester_id = request_item["requester_id"]

    try:
        sandbox = provisioner.create_sandbox(
            request_id=request_id,
            owner_name=request_item["requester_name"],
            owner_slack_id=requester_id,
            duration_minutes=request_item["duration_minutes"],
        )
    except Exception as error:
        logger.exception("Failed to provision sandbox %s", request_id)
        request_store.update_request(request_id, request_store.STATUS_FAILED, {"error_message": str(error)})
        slack.post_message(requester_id, f"Sorry, creating sandbox `{request_id}` failed. Please contact the platform team.")
        return {"status": request_store.STATUS_FAILED}

    request_store.update_request(
        request_id,
        request_store.STATUS_ACTIVE,
        {
            "bucket_name": sandbox["bucket_name"],
            "role_arn": sandbox["role_arn"],
            "expires_at": sandbox["expires_at"],
        },
    )
    logger.info("Sandbox %s is active until %s", request_id, sandbox["expires_at"])

    slack.post_message(requester_id, build_ready_message(request_id, sandbox))
    return {"status": request_store.STATUS_ACTIVE, "sandbox": sandbox}
