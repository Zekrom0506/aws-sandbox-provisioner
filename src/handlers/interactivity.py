import json
import logging

import boto3

from sandbox import config, request_store, slack

logger = logging.getLogger()
logger.setLevel(logging.INFO)

APPROVE_ACTION = "approve_sandbox"
DENY_ACTION = "deny_sandbox"


def start_provisioning(request_id):
    # Slack expects an answer within 3 seconds, so the slow work runs in a separate Lambda.
    lambda_client = boto3.client("lambda")
    lambda_client.invoke(
        FunctionName=config.get_provisioner_function_name(),
        InvocationType="Event",
        Payload=json.dumps({"request_id": request_id}).encode("utf-8"),
    )


def replace_approval_message(response_url, text):
    slack.post_to_response_url(response_url, {"replace_original": True, "text": text})


def lambda_handler(event, context):
    if not slack.is_valid_signature(event, config.get_slack_signing_secret()):
        logger.warning("Rejected interaction with an invalid Slack signature")
        return slack.build_http_response(401, {"error": "invalid signature"})

    form = slack.parse_form_body(event)
    payload = json.loads(form["payload"])

    action = payload["actions"][0]
    action_id = action["action_id"]
    request_id = action["value"]
    manager_id = payload["user"]["id"]
    response_url = payload["response_url"]

    if manager_id not in config.get_manager_slack_ids():
        logger.warning("User %s is not allowed to approve sandbox requests", manager_id)
        slack.post_to_response_url(
            response_url,
            {"response_type": "ephemeral", "replace_original": False, "text": "Only managers can approve sandboxes."},
        )
        return slack.build_http_response(200, {})

    if action_id == APPROVE_ACTION:
        new_status = request_store.STATUS_APPROVED
    elif action_id == DENY_ACTION:
        new_status = request_store.STATUS_DENIED
    else:
        logger.warning("Unknown action %s", action_id)
        return slack.build_http_response(400, {"error": "unknown action"})

    was_updated = request_store.mark_pending_request_decided(request_id, new_status, manager_id)
    if not was_updated:
        logger.info("Request %s was already decided", request_id)
        return slack.build_http_response(200, {})

    request_item = request_store.get_request(request_id)
    requester_id = request_item["requester_id"]

    if new_status == request_store.STATUS_APPROVED:
        start_provisioning(request_id)
        replace_approval_message(
            response_url,
            f"Sandbox `{request_id}` for <@{requester_id}> was approved by <@{manager_id}>. Provisioning started.",
        )
    else:
        replace_approval_message(
            response_url,
            f"Sandbox `{request_id}` for <@{requester_id}> was denied by <@{manager_id}>.",
        )
        slack.post_message(requester_id, f"Your sandbox request `{request_id}` was denied by <@{manager_id}>.")

    return slack.build_http_response(200, {})
