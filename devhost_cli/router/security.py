# devhost_cli/router/security.py - Security validation module
import ipaddress
import logging
import os
import re
import socket

logger = logging.getLogger("devhost.security")

# RFC 1035/1123: Length limits for DNS names
# https://datatracker.ietf.org/doc/html/rfc1035 (Section 2.3.4)
# https://datatracker.ietf.org/doc/html/rfc1123 (Section 2.1)
MAX_HOSTNAME_LENGTH = 253  # Maximum total hostname length (RFC 1035)
MAX_LABEL_LENGTH = 63      # Maximum length of a single DNS label (RFC 1035)
MAX_ROUTE_NAME_LENGTH = 63 # Maximum length for route/subdomain names (same as DNS label)

# RFC 1918 private networks + link-local
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
]

METADATA_HOSTNAMES = [
    "metadata.google.internal",
    "169.254.169.254",
    "metadata",
]

VALID_SUBDOMAIN_PATTERN = re.compile(r"^(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)$", re.IGNORECASE)


def validate_upstream_target(host: str, port: int) -> tuple[bool, str | None]:
    if os.getenv("DEVHOST_ALLOW_PRIVATE_NETWORKS", "").lower() in {"1", "true"}:
        return (True, None)

    if host.lower() in METADATA_HOSTNAMES:
        return (False, f"Target {host} is a blocked metadata endpoint (SSRF protection)")

    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    except Exception as e:
        logger.warning("Failed to resolve %s: %s", host, e)
        return (False, f"Cannot resolve hostname: {host}")

    for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for network in BLOCKED_NETWORKS:
            if ip_obj in network:
                logger.warning("Blocked private IP: %s (%s) in %s", host, ip_str, network)
                return (
                    False,
                    f"Target {host} resolves to private IP {ip_str} (SSRF protection). Use DEVHOST_ALLOW_PRIVATE_NETWORKS=1 to override.",
                )

    return (True, None)


def validate_hostname(hostname: str) -> tuple[bool, str | None]:
    if not hostname:
        return (False, "Hostname cannot be empty")

    if any(c in hostname for c in ["\r", "\n", "\x00"]):
        return (False, "Hostname contains invalid control characters")

    if not all(c.isalnum() or c in ".-" for c in hostname):
        return (False, "Hostname contains invalid characters")

    if len(hostname) > MAX_HOSTNAME_LENGTH:
        return (False, f"Hostname too long: {len(hostname)} chars (max {MAX_HOSTNAME_LENGTH} per RFC 1035)")

    labels = hostname.split(".")
    for label in labels:
        if len(label) > MAX_LABEL_LENGTH:
            return (False, f"Label '{label}' too long: {len(label)} chars (max {MAX_LABEL_LENGTH} per RFC 1035)")
        if not label:
            return (False, "Empty label in hostname")

    if not VALID_SUBDOMAIN_PATTERN.match(hostname.split(".")[0]):
        return (False, "Hostname does not meet RFC 1123 requirements")

    return (True, None)
