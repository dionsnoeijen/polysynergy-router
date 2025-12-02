"""
Request parser for extracting project_id and stage from HTTP requests.

Supports two formats:
1. Subdomain-based (production): project-123-dev.domain.com/api/users
2. Path-based (self-hosted): domain.com/project-123/dev/api/users
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedRequest:
    """Parsed request information."""
    project_id: str
    stage: str
    path: str  # The actual path without project/stage prefix
    routing_method: str  # 'subdomain' or 'path'


class RequestParser:
    """
    Parse HTTP requests to extract project_id, stage, and path.

    Subdomain format:
        Host: project-123-dev.domain.com
        Path: /api/users
        → project_id=project-123, stage=dev, path=/api/users

    Path-based format:
        Host: domain.com
        Path: /project-123/dev/api/users
        → project_id=project-123, stage=dev, path=/api/users

    *.localhost support:
        Host: project-123-dev.localhost:8080
        → project_id=project-123, stage=dev
    """

    # Subdomain pattern: {project_id}-{stage}.{domain}
    # Examples:
    #   myproject-dev.polysynergy.com
    #   test-123-staging.polysynergy.com
    #   project-prod.localhost
    SUBDOMAIN_PATTERN = re.compile(r'^([a-zA-Z0-9_-]+)-([a-zA-Z0-9_-]+)\.')

    # Path-based pattern: /{project_id}/{stage}/{rest_of_path}
    # Examples:
    #   /myproject/dev/api/users
    #   /test-123/staging/api/users
    PATH_BASED_PATTERN = re.compile(r'^/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(/.*)?$')

    @classmethod
    def parse_request(cls, host: str, path: str) -> Optional[ParsedRequest]:
        """
        Parse HTTP request to extract project_id, stage, and actual path.

        Args:
            host: HTTP Host header (e.g., "project-dev.domain.com" or "domain.com")
            path: HTTP path (e.g., "/api/users" or "/project/dev/api/users")

        Returns:
            ParsedRequest if successfully parsed, None otherwise
        """
        # Try subdomain parsing first
        result = cls._parse_subdomain(host, path)
        if result:
            return result

        # Fall back to path-based parsing
        result = cls._parse_path_based(host, path)
        if result:
            return result

        return None

    @classmethod
    def _parse_subdomain(cls, host: str, path: str) -> Optional[ParsedRequest]:
        """
        Parse subdomain-based routing.

        Examples:
            Host: myproject-dev.polysynergy.com, Path: /api/users
            → project_id=myproject, stage=dev, path=/api/users

            Host: test-staging.localhost:8080, Path: /api/test
            → project_id=test, stage=staging, path=/api/test
        """
        # Remove port if present
        host_without_port = host.split(':')[0]

        match = cls.SUBDOMAIN_PATTERN.match(host_without_port)
        if not match:
            return None

        project_id = match.group(1)
        stage = match.group(2)

        return ParsedRequest(
            project_id=project_id,
            stage=stage,
            path=path,
            routing_method='subdomain'
        )

    @classmethod
    def _parse_path_based(cls, host: str, path: str) -> Optional[ParsedRequest]:
        """
        Parse path-based routing.

        Examples:
            Host: localhost, Path: /myproject/dev/api/users
            → project_id=myproject, stage=dev, path=/api/users

            Host: domain.com, Path: /test/staging/api/test
            → project_id=test, stage=staging, path=/api/test
        """
        match = cls.PATH_BASED_PATTERN.match(path)
        if not match:
            return None

        project_id = match.group(1)
        stage = match.group(2)
        actual_path = match.group(3) or '/'

        return ParsedRequest(
            project_id=project_id,
            stage=stage,
            path=actual_path,
            routing_method='path'
        )

    @classmethod
    def is_subdomain_routing(cls, host: str) -> bool:
        """Check if request uses subdomain routing."""
        host_without_port = host.split(':')[0]
        return bool(cls.SUBDOMAIN_PATTERN.match(host_without_port))

    @classmethod
    def is_path_based_routing(cls, path: str) -> bool:
        """Check if request uses path-based routing."""
        return bool(cls.PATH_BASED_PATTERN.match(path))


# Convenience function for quick parsing
def parse_request(host: str, path: str) -> Optional[ParsedRequest]:
    """
    Parse HTTP request to extract project_id, stage, and path.

    Usage:
        from routing.request_parser import parse_request

        result = parse_request("myproject-dev.localhost", "/api/users")
        if result:
            print(f"Project: {result.project_id}")
            print(f"Stage: {result.stage}")
            print(f"Path: {result.path}")
    """
    return RequestParser.parse_request(host, path)
