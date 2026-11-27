"""AWS Lambda entry point for ConquestRunner."""

from capture_lambda import lambda_handler as capture_lambda_handler


def lambda_handler(event, context):
    return capture_lambda_handler(event, context)
