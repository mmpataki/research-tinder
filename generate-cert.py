"""
Generate a self-signed SSL certificate for Research Tinder.

Creates cert.pem + key.pem in the backend/ directory so uvicorn can
serve over HTTPS — required for PWA install on LAN devices.

Usage:
    python generate-cert.py                     # cert for localhost + auto-detected LAN IPs
    python generate-cert.py 192.168.1.50        # cert for a specific IP too

The cert is valid for 365 days and covers:
    - localhost / 127.0.0.1
    - your machine's hostname
    - all detected LAN IPs (or the one you specify)
"""

import sys
import socket
import datetime
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Error: 'cryptography' package is required.")
    print("Install it with:  pip install cryptography")
    sys.exit(1)


def get_lan_ips():
    """Return a list of non-loopback IPv4 addresses for this machine."""
    ips = []
    try:
        # Connect to a public DNS to find the default outbound IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    # Also try getaddrinfo for the hostname
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if addr not in ips and not addr.startswith("127."):
                ips.append(addr)
    except Exception:
        pass

    return ips


def generate_cert(extra_ips=None, out_dir=None):
    if out_dir is None:
        out_dir = Path(__file__).parent / "backend"
    else:
        out_dir = Path(out_dir)

    cert_path = out_dir / "cert.pem"
    key_path = out_dir / "key.pem"

    # Gather SANs (Subject Alternative Names)
    hostname = socket.gethostname()
    lan_ips = get_lan_ips()
    if extra_ips:
        for ip in extra_ips:
            if ip not in lan_ips:
                lan_ips.append(ip)

    san_dns = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
    ]
    san_ips = [
        x509.IPAddress(ipaddress_parse("127.0.0.1")),
    ]
    for ip in lan_ips:
        san_ips.append(x509.IPAddress(ipaddress_parse(ip)))

    # Generate RSA key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Research Tinder Dev"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Research Tinder"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san_dns + san_ips),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )

    # Write files
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print("=" * 60)
    print("  SSL certificate generated!")
    print("=" * 60)
    print(f"  Certificate : {cert_path}")
    print(f"  Private key : {key_path}")
    print(f"  Valid for   : 365 days")
    print(f"  Hostname    : {hostname}")
    print(f"  LAN IPs     : {', '.join(lan_ips) if lan_ips else '(none detected)'}")
    print()
    print("  Covered addresses (SANs):")
    print(f"    - https://localhost:8000")
    for ip in lan_ips:
        print(f"    - https://{ip}:8000")
    print()
    print("  NOTE: Browsers will show a security warning for self-signed")
    print("  certs. To bypass on Chrome: click 'Advanced' > 'Proceed'.")
    print()
    print("  For trusted certs (no warnings), install mkcert:")
    print("    https://github.com/FiloSottile/mkcert")
    print("    Then run: mkcert -install && mkcert localhost 127.0.0.1 <LAN-IP>")
    print("=" * 60)


def ipaddress_parse(addr):
    """Parse an IP address string into an ipaddress object."""
    import ipaddress
    return ipaddress.ip_address(addr)


if __name__ == "__main__":
    extra = sys.argv[1:] if len(sys.argv) > 1 else None
    generate_cert(extra_ips=extra)
