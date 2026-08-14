"""Resolve client addresses without trusting arbitrary forwarding headers."""

from __future__ import annotations

from ipaddress import ip_address, ip_network


def resolve_client_ip(peer_ip: str | None, forwarded_for: str | None, trusted_proxy_ips: tuple[str, ...]) -> str:
    peer = (peer_ip or "").strip()
    try:
        parsed_peer = ip_address(peer)
    except ValueError:
        return "unknown"
    trusted = any(parsed_peer in ip_network(network, strict=False) for network in trusted_proxy_ips)
    if not trusted or not forwarded_for:
        return str(parsed_peer)
    first = forwarded_for.split(",", 1)[0].strip()
    try:
        return str(ip_address(first))
    except ValueError:
        return str(parsed_peer)
