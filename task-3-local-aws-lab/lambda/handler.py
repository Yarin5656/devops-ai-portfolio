"""
s3-event-processor
------------------
Triggered by S3 ObjectCreated events via LocalStack.
Extracts the uploaded file name and sends a structured
message to SQS for downstream processing.
"""

import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Injected by Terraform
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]

# LocalStack endpoint — present when running locally; absent on real AWS
LOCALSTACK_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", None)

sqs = boto3.client(
    "sqs",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    endpoint_url=LOCALSTACK_ENDPOINT,
    # LocalStack accepts any credentials
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
)


def lambda_handler(event: dict, context) -> dict:
    """Entry point invoked by the S3 event notification."""
    logger.info("Received event: %s", json.dumps(event))

    processed = 0
    errors = 0

    for record in event.get("Records", []):
        try:
            bucket = record["s3"]["bucket"]["name"]
            # S3 URL-encodes object keys (spaces become '+' etc.)
            key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
            size = record["s3"]["object"].get("size", 0)
            event_time = record.get("eventTime", datetime.now(timezone.utc).isoformat())

            logger.info("Processing upload: bucket=%s key=%s size=%d", bucket, key, size)

            message = {
                "source": "s3-event-processor",
                "event_time": event_time,
                "bucket": bucket,
                "file_name": key,
                "file_size_bytes": size,
                "status": "uploaded",
            }

            response = sqs.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    "source": {
                        "StringValue": "lambda-s3-processor",
                        "DataType": "String",
                    },
                    "bucket": {
                        "StringValue": bucket,
                        "DataType": "String",
                    },
                },
            )

            logger.info(
                "Message sent to SQS: MessageId=%s file=%s",
                response["MessageId"],
                key,
            )
            processed += 1

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to process record: %s | error: %s", record, exc, exc_info=True)
            errors += 1

    summary = {"processed": processed, "errors": errors}
    logger.info("Lambda execution complete: %s", summary)
    return {"statusCode": 200, "body": json.dumps(summary)}
