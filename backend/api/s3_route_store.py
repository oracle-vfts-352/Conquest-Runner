"""Stores a route in Amazon S3 (the 'claim check').

This follows the PROPOSAL in docs/API_CONTRACT.md section 4.3. It is not a final
team decision. If the team chooses another design, only this file changes.

The S3 client is passed in, so tests can use a fake client without AWS.
Bucket policy, encryption settings and lifecycle rules belong to the
infrastructure (infrastructure/template.yaml), not to this file.
"""

import json
import re

from botocore.exceptions import BotoCoreError, ClientError

from capture_service import format_timestamp
from models import GpsSample
from ports import RouteObject, StorageUnavailableError

ROUTE_FORMAT_VERSION = 1

# Only these characters may appear in a storage key part. This stops an
# unexpected identifier from changing the key's folder structure.
SAFE_KEY_PART = re.compile(r"[A-Za-z0-9_-]{1,128}")


class S3RouteStore:
    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(
        self, player_id: str, capture_id: str, samples: list[GpsSample]
    ) -> RouteObject:
        """Save the route. The same input always gives the same key, so saving
        again (a retry) just overwrites the same object."""
        if not SAFE_KEY_PART.fullmatch(player_id) or not SAFE_KEY_PART.fullmatch(
            capture_id
        ):
            raise ValueError("Unsupported identifier for a storage key.")

        key = f"captures/{player_id}/{capture_id}/route.json"
        document = {
            "schemaVersion": ROUTE_FORMAT_VERSION,
            "route": [
                {
                    "latitude": sample.latitude,
                    "longitude": sample.longitude,
                    "timestamp": format_timestamp(sample.timestamp),
                    "accuracyMeters": sample.accuracy_meters,
                }
                for sample in samples
            ],
        }

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=json.dumps(document, separators=(",", ":")).encode("utf-8"),
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
        except (BotoCoreError, ClientError) as error:
            # Keep AWS error details out of the message: they are not needed
            # by the caller and must never reach the client.
            raise StorageUnavailableError("The route store is unavailable.") from error

        return RouteObject(bucket=self._bucket, key=key)
