import logging
from datetime import datetime, timezone

import boto3

from sandbox import cleanup, request_store, slack

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def notify_owner(request_id):
    request_item = request_store.get_request(request_id)
    if request_item is None:
        return
    try:
        slack.post_message(request_item["requester_id"], f"Your sandbox `{request_id}` expired and has been deleted.")
    except Exception:
        # A failed Slack message should not stop the rest of the cleanup.
        logger.exception("Could not notify owner of sandbox %s", request_id)


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    s3_client = boto3.client("s3")
    iam_client = boto3.client("iam")

    cleaned_request_ids = cleanup.delete_expired_sandboxes(s3_client, iam_client, now)

    for request_id in cleaned_request_ids:
        request_store.update_request(request_id, request_store.STATUS_EXPIRED)
        notify_owner(request_id)

    logger.info("Cleanup finished, deleted %d sandbox(es)", len(cleaned_request_ids))
    return {"deleted_request_ids": cleaned_request_ids}
