"""URL normalization and public-network validation. No DNS during extraction."""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

_suffixes = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)
TRACKING = {"fbclid", "gclid", "msclkid"}


def normalize_url(value: str, *, homepage: bool = False) -> str:
    value = value.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError("Enter an HTTP or HTTPS URL.")
    if "://" not in value:
        value = "https://" + value
    p = urlsplit(value)
    if (
        p.scheme.lower() not in {"https", "http"}
        or not p.hostname
        or p.username
        or p.password
    ):
        raise ValueError("Only public HTTP(S) URLs without credentials are supported.")
    host = p.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if p.port not in {None, 80, 443}:
        raise ValueError("Only standard web ports are supported.")
    if "." not in host or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise ValueError("A public website hostname is required.")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Private addresses are not allowed.")
    except ValueError as exc:
        if "Private addresses" in str(exc):
            raise
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("Invalid hostname.")
    path = "/" if homepage else (p.path or "/")
    query = (
        ""
        if homepage
        else urlencode(
            [
                (k, v)
                for k, v in parse_qsl(p.query, keep_blank_values=True)
                if not k.lower().startswith("utm_") and k.lower() not in TRACKING
            ]
        )
    )
    # Retain explicit non-default standard ports: http:443 is not https.
    default_port = 443 if p.scheme == "https" else 80
    authority = host + (f":{p.port}" if p.port and p.port != default_port else "")
    return urlunsplit((p.scheme.lower(), authority, path, query, ""))


def host_of(url: str) -> str:
    return urlsplit(url).hostname or ""


def known_domain(domain: str) -> bool:
    """Syntax-level public suffix check using the bundled list, without DNS."""
    result = _suffixes(domain)
    return bool(result.domain and result.suffix)


def origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def same_site(a: str, b: str) -> bool:
    # Private suffix handling keeps independent myshopify tenants separate.
    x, y = _suffixes(host_of(a)), _suffixes(host_of(b))
    return bool(
        x.top_domain_under_public_suffix
        and x.top_domain_under_public_suffix == y.top_domain_under_public_suffix
    )


async def public_addresses(host: str) -> list[str]:
    try:
        info = await asyncio.get_running_loop().getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise ValueError(f"DNS lookup failed for {host}") from exc
    addresses = list(dict.fromkeys(row[4][0] for row in info))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("DNS resolved to a non-public address.")
    return sorted(addresses, key=lambda value: ":" in value)
