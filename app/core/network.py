from __future__ import annotations

import socket


def get_lan_ip() -> str:
    """Return a LAN-reachable IPv4 address when one can be detected."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def display_host_for_browser(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return get_lan_ip()
    return host


def build_browser_urls(*, host: str, port: int) -> dict[str, str]:
    display_host = display_host_for_browser(host)
    base_url = f"http://{display_host}:{port}"
    return {
        "base_url": base_url,
        "dashboard_url": f"{base_url}/dashboard",
        "settings_url": f"{base_url}/settings",
    }
