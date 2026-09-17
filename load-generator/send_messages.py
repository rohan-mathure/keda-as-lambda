#!/usr/bin/env python3
"""
Send test messages to LocalStack SQS or SNS.
"""

import argparse
import json
import sys
from datetime import datetime

import boto3


def send_sqs_messages(endpoint, queue_name, count):
    """Send messages to SQS queue."""
    client = boto3.client(
        'sqs',
        endpoint_url=endpoint,
        region_name='us-east-1',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )

    # Get queue URL
    response = client.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']

    print(f"Sending {count} messages to SQS queue: {queue_name}")

    for i in range(count):
        message = {
            "id": i + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Test message {i + 1}"
        }

        try:
            client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            print(f"  [{i + 1}/{count}] Sent: {message['message']}")
        except Exception as e:
            print(f"Error sending message {i + 1}: {e}", file=sys.stderr)
            return False

    print(f"\n✓ Successfully sent {count} messages to {queue_name}")
    return True


def send_sns_messages(endpoint, topic_name, count):
    """Send messages to SNS topic."""
    client = boto3.client(
        'sns',
        endpoint_url=endpoint,
        region_name='us-east-1',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )

    # Get topic ARN (LocalStack format)
    topic_arn = f"arn:aws:sns:us-east-1:000000000000:{topic_name}"

    print(f"Publishing {count} messages to SNS topic: {topic_name}")

    for i in range(count):
        message = {
            "id": i + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Test message {i + 1}"
        }

        try:
            client.publish(
                TopicArn=topic_arn,
                Message=json.dumps(message)
            )
            print(f"  [{i + 1}/{count}] Published: {message['message']}")
        except Exception as e:
            print(f"Error publishing message {i + 1}: {e}", file=sys.stderr)
            return False

    print(f"\n✓ Successfully published {count} messages to {topic_name}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Send test messages to LocalStack SQS or SNS"
    )
    parser.add_argument(
        '--endpoint',
        default='http://localhost:4566',
        help='LocalStack endpoint URL (default: http://localhost:4566)'
    )
    parser.add_argument(
        '--queue',
        help='SQS queue name (mutually exclusive with --topic)'
    )
    parser.add_argument(
        '--topic',
        help='SNS topic name (mutually exclusive with --queue)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=1,
        help='Number of messages to send (default: 1)'
    )

    args = parser.parse_args()

    if args.queue and args.topic:
        print("Error: cannot specify both --queue and --topic", file=sys.stderr)
        sys.exit(1)

    if not args.queue and not args.topic:
        print("Error: must specify either --queue or --topic", file=sys.stderr)
        sys.exit(1)

    if args.count <= 0:
        print("Error: count must be > 0", file=sys.stderr)
        sys.exit(1)

    try:
        if args.queue:
            success = send_sqs_messages(args.endpoint, args.queue, args.count)
        else:
            success = send_sns_messages(args.endpoint, args.topic, args.count)

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
