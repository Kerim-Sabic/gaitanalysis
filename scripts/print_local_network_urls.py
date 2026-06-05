"""Print likely LAN IPs + exact commands for a same-Wi-Fi phone QR demo.

    python scripts/print_local_network_urls.py

A phone cannot reach http://localhost on the laptop — use the laptop's LAN IP
(or a deployed URL). Ends with LOCAL PHONE DEMO URLS READY.
"""
from __future__ import annotations

import socket

import _bootstrap  # noqa: F401


def candidate_ips() -> list[str]:
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    # Best-effort primary route IP (no traffic actually sent).
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    lan = sorted(ip for ip in ips if ip.startswith(("192.168.", "10.")) or ip.startswith("172."))
    return lan or sorted(ips)


def main() -> int:
    ips = candidate_ips()
    primary = ips[0] if ips else "YOUR_LAN_IP"
    print("=== Local phone-demo network URLs ===")
    print(f"Detected LAN IP(s): {', '.join(ips) or '(none found — check Wi-Fi)'}")
    print(f"\nUse this IP for the phone demo: {primary}\n")

    print("# Backend (bind to all interfaces so the phone can reach it):")
    print("cd apps/api")
    print(".venv\\Scripts\\activate")
    print('$env:HORALIX_POSE_BACKEND="auto_best"; $env:HORALIX_AUTO_BEST_MODE="fast"')
    print('$env:HORALIX_ENABLE_SAM2="true"; $env:HORALIX_SEGMENTATION_BACKEND="sam2"')
    print('$env:HORALIX_ENABLE_DEPTH="true"; $env:HORALIX_DEPTH_BACKEND="depth_anything_v2"')
    print(f'$env:HORALIX_CORS_ORIGINS="http://{primary}:3000"')
    print("uvicorn app.main:app --host 0.0.0.0 --port 8010")

    print("\n# Frontend (PowerShell):")
    print("cd apps/web")
    print(f'$env:NEXT_PUBLIC_API_URL="http://{primary}:8010"')
    print(f'$env:NEXT_PUBLIC_APP_URL="http://{primary}:3000"')
    print("npm run dev -- --hostname 0.0.0.0")

    print("\n# Frontend (bash/cmd):")
    print(f"set NEXT_PUBLIC_API_URL=http://{primary}:8010")
    print(f"set NEXT_PUBLIC_APP_URL=http://{primary}:3000")
    print("npm run dev -- --hostname 0.0.0.0")

    print(f"\nPhone opens:  http://{primary}:3000  -> 'Use phone camera' -> scan QR")
    print("(Phone and laptop must be on the same Wi-Fi. For HTTPS-only phone cameras,")
    print(" deploy the frontend to Netlify and point NEXT_PUBLIC_API_URL at a public backend.)")
    print("\nLOCAL PHONE DEMO URLS READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
