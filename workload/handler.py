#!/usr/bin/env python3
"""
Lambda-like job handler for KEDA ScaledJob.
Simulates processing a single SQS message.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """
    Mimics AWS Lambda handler signature.
    Args:
        event: dict with message body
        context: ignored (for compatibility)
    Returns: dict with statusCode
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Simulate work
        processing_time = 0.5 + (hash(str(event)) % 10) * 0.1
        logger.info(f"Processing for {processing_time:.1f}s...")
        time.sleep(processing_time)

        logger.info("Processing complete.")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "success",
                "processed_at": datetime.utcnow().isoformat()
            })
        }
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def main():
    """Entry point when run directly."""
    # For KEDA ScaledJob, the message body is passed via env var
    # In a real scenario with SQS integration, KEDA would inject it
    message_body = os.environ.get('MESSAGE_BODY', '{}')

    try:
        event = json.loads(message_body)
    except json.JSONDecodeError:
        event = {"body": message_body}

    result = lambda_handler(event, None)

    if result.get("statusCode") != 200:
        logger.error(f"Handler returned error: {result}")
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
