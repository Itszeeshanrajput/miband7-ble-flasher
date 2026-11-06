import os
import subprocess
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parent.parent / "native"

class ECDHAuthEngine:
    """
    Handles NIST B-163 Elliptic Curve Diffie-Hellman (ECDH) key agreement
    and AES-128 cryptographic challenge-response for Zepp OS wearables.
    """
    def __init__(self, auth_key_hex: str):
        # Normalize auth key (strip 0x prefix if present)
        clean_key = auth_key_hex.lower().replace("0x", "").strip()
        if len(clean_key) != 32:
            raise ValueError(f"Auth key must be exactly 32 hex characters (16 bytes), got {len(clean_key)}")
        self.auth_key = clean_key
        self.private_ec = os.urandom(24)
        self.public_ec = None
        self._ensure_compiled()

    def _ensure_compiled(self):
        class_file = NATIVE_DIR / "AuthHelper.class"
        java_file = NATIVE_DIR / "AuthHelper.java"
        if not class_file.exists():
            subprocess.run(["javac", str(java_file)], check=True, cwd=str(NATIVE_DIR))

    def generate_public_key(self) -> bytes:
        """
        Generates 48-byte ECDH B-163 public key point (X, Y) from private key.
        """
        pub_hex = subprocess.check_output(
            ["java", "-cp", str(NATIVE_DIR), "AuthHelper", "genpub", self.private_ec.hex()]
        ).decode().strip()
        self.public_ec = bytes.fromhex(pub_hex)
        return self.public_ec

    def compute_challenge_response(self, remote_public_bytes: bytes, remote_random_bytes: bytes) -> bytes:
        """
        Performs ECDH shared secret derivation, derives session key,
        and double-encrypts the random challenge using AES-128 ECB.
        """
        out = subprocess.check_output([
            "java", "-cp", str(NATIVE_DIR), "AuthHelper", "compute",
            self.private_ec.hex(),
            remote_public_bytes.hex(),
            remote_random_bytes.hex(),
            self.auth_key
        ]).decode().strip()

        lines = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        if "CMD" not in lines:
            raise RuntimeError(f"Cryptographic derivation failed: {out}")
        return bytes.fromhex(lines["CMD"])
