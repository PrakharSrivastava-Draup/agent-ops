from __future__ import annotations

import asyncio
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.utils.sanitization import sanitize_path, validate_bucket_name, validate_region


class AWSAgent(BaseAgent):
    """Read-only AWS agent using boto3."""

    def __init__(
        self,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        super().__init__("AWSAgent")
        session_kwargs: dict[str, Any] = {}
        if access_key_id and secret_access_key:
            session_kwargs = {
                "aws_access_key_id": access_key_id,
                "aws_secret_access_key": secret_access_key,
            }
        self.session = boto3.Session(**session_kwargs)
        self._log_info("Initialized AWS agent", using_env=not bool(session_kwargs))

    async def list_s3_buckets(self) -> AgentResponse:
        """List available S3 buckets."""

        def _list_buckets() -> list[str]:
            client = self.session.client("s3")
            response = client.list_buckets()
            buckets = response.get("Buckets", [])
            return [bucket["Name"] for bucket in buckets[:50]]

        try:
            buckets = await asyncio.to_thread(_list_buckets)
        except (ClientError, BotoCoreError) as exc:
            self._log_error("Failed to list S3 buckets", error=str(exc))
            raise AgentError("Failed to list S3 buckets.") from exc
        return AgentResponse(data={"buckets": buckets})

    async def describe_ec2_instances(self, region: str) -> AgentResponse:
        """Describe EC2 instances in a region."""
        validate_region(region)

        def _describe() -> list[dict[str, Any]]:
            client = self.session.client("ec2", region_name=region)
            paginator = client.get_paginator("describe_instances")
            details: list[dict[str, Any]] = []
            for page in paginator.paginate(PaginationConfig={"MaxItems": 50}):
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        details.append(
                            {
                                "instance_id": instance.get("InstanceId"),
                                "type": instance.get("InstanceType"),
                                "state": instance.get("State", {}).get("Name"),
                                "launch_time": instance.get("LaunchTime"),
                            }
                        )
                        if len(details) >= 50:
                            return details
            return details

        try:
            instances = await asyncio.to_thread(_describe)
        except (ClientError, BotoCoreError) as exc:
            self._log_error("Failed to describe EC2 instances", region=region, error=str(exc))
            raise AgentError("Failed to describe EC2 instances.") from exc
        return AgentResponse(data={"instances": instances})

    async def get_s3_object_head(self, bucket: str, key: str) -> AgentResponse:
        """Retrieve S3 object metadata without downloading content."""
        validate_bucket_name(bucket)
        sanitize_path(key)

        def _head() -> dict[str, Any]:
            client = self.session.client("s3")
            response = client.head_object(Bucket=bucket, Key=key)
            return {
                "bucket": bucket,
                "key": key,
                "size": response.get("ContentLength"),
                "content_type": response.get("ContentType"),
                "etag": response.get("ETag"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }

        try:
            metadata = await asyncio.to_thread(_head)
        except (ClientError, BotoCoreError) as exc:
            self._log_error(
                "Failed to retrieve S3 object head",
                bucket=bucket,
                key=key,
                error=str(exc),
            )
            raise AgentError("Failed to retrieve S3 object metadata.") from exc
        return AgentResponse(data=metadata)


