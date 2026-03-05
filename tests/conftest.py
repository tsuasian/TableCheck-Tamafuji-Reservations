import os

import pytest

# Ensure tests don't hit real AWS
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "test-table")


@pytest.fixture
def dynamodb_table():
    """Create a moto DynamoDB table matching the single-table schema."""
    from moto import mock_aws

    with mock_aws():
        import boto3

        ddb = boto3.resource("dynamodb", region_name="us-west-2")
        table = ddb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="test-table")
        yield table
