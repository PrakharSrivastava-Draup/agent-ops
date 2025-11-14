from __future__ import annotations

import ipaddress
import re
from typing import Iterable
from urllib.parse import urlparse


PRIVATE_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
)


def ensure_safe_url(url: str, allowed_hosts: Iterable[str]) -> None:
    """Validate URL to prevent SSRF to private networks."""
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Only HTTP/HTTPS URLs are allowed.")
    if parsed.hostname is None:
        raise ValueError("URL must include hostname.")
    hostname = parsed.hostname.lower()
    if hostname not in {host.lower() for host in allowed_hosts}:
        raise ValueError("Hostname is not in allowed list.")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if any(ip in network for network in PRIVATE_NETS):
        raise ValueError("IP address is not allowed.")


def sanitize_path(path: str) -> str:
    """Ensure API paths do not traverse directories."""
    if ".." in path or path.startswith("/"):
        raise ValueError("Path contains invalid traversal characters.")
    return path


def _validate_name(name: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError(f"{label} contains invalid characters.")
    return name


def validate_owner_name(name: str) -> str:
    """Validate repository owner name."""
    return _validate_name(name, "Owner name")


def validate_repo_name(name: str) -> str:
    """Validate repository name characters."""
    return _validate_name(name, "Repository name")


def validate_branch_name(name: str) -> str:
    """Validate branch name."""
    if not name or " " in name:
        raise ValueError("Branch name is invalid.")
    return name


def validate_region(name: str) -> str:
    """Validate AWS region format."""
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", name):
        raise ValueError("Region format is invalid.")
    return name


def validate_bucket_name(name: str) -> str:
    """Validate S3 bucket name."""
    if not re.fullmatch(r"[a-z0-9.-]{3,63}", name):
        raise ValueError("Bucket name is invalid.")
    return name


def validate_issue_key(issue_key: str) -> str:
    """Validate Jira issue key."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+-\d+", issue_key):
        raise ValueError("Issue key is invalid.")
    return issue_key


def sanitize_jql(jql: str) -> str:
    """Basic validation to reduce injection risk."""
    if ";" in jql or "--" in jql:
        raise ValueError("JQL contains forbidden tokens.")
    if len(jql) > 500:
        raise ValueError("JQL query too long.")
    return jql

