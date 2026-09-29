import uuid
from datetime import datetime, timezone

import boto3

from sandbox import config
from sandbox.tags import format_time

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_DENIED = "DENIED"
STATUS_ACTIVE = "ACTIVE"
STATUS_FAILED = "FAILED"
STATUS_EXPIRED = "EXPIRED"


def get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(config.get_table_name())


def create_request(requester_id, requester_name, duration_minutes, reason):
    request_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    item = {
        "request_id": request_id,
        "requester_id": requester_id,
        "requester_name": requester_name,
        "duration_minutes": duration_minutes,
        "reason": reason,
        "status": STATUS_PENDING,
        "created_at": format_time(now),
    }

    table = get_table()
    table.put_item(Item=item)
    return item


def get_request(request_id):
    table = get_table()
    response = table.get_item(Key={"request_id": request_id})
    return response.get("Item")


def update_request(request_id, new_status, extra_fields=None):
    if extra_fields is None:
        extra_fields = {}

    fields_to_set = {"status": new_status, "updated_at": format_time(datetime.now(timezone.utc))}
    for key, value in extra_fields.items():
        fields_to_set[key] = value

    # "status" is a DynamoDB reserved word, so every field goes through name placeholders.
    expression_parts = []
    attribute_names = {}
    attribute_values = {}
    for index, (key, value) in enumerate(fields_to_set.items()):
        name_placeholder = f"#field{index}"
        value_placeholder = f":value{index}"
        expression_parts.append(f"{name_placeholder} = {value_placeholder}")
        attribute_names[name_placeholder] = key
        attribute_values[value_placeholder] = value

    table = get_table()
    table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET " + ", ".join(expression_parts),
        ExpressionAttributeNames=attribute_names,
        ExpressionAttributeValues=attribute_values,
    )


def mark_pending_request_decided(request_id, new_status, manager_id):
    """Only moves a request out of PENDING once, so a double click cannot provision twice."""
    table = get_table()
    try:
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #status = :new_status, decided_by = :manager, updated_at = :now",
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":new_status": new_status,
                ":manager": manager_id,
                ":now": format_time(datetime.now(timezone.utc)),
                ":pending": STATUS_PENDING,
            },
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False
