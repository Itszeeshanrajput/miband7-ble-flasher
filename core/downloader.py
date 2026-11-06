import os
import zlib
import zipfile
import requests
from typing import Dict, Optional

OFFICIAL_FIRMWARES = {
    "2.2.0.1-std": {
        "version": "2.2.0.1",
        "type": "Standard (M2129B1)",
        "url": "https://cdn.cnbj2.fds.api.mi-img.com/hm-artifact-plat/firmware/20240130/1706606869152/fw_20240130172749_46312.zip",
        "size": 23539837,
        "crc32": 0x978d2100,
        "filename": "miband7_std_2.2.0.1.zip"
    },
    "2.2.0.1-nfc": {
        "version": "2.2.0.1",
        "type": "NFC (M2130B1)",
        "url": "https://cdn.cnbj2.fds.api.mi-img.com/hm-artifact-plat/firmware/20240130/1706606869152/fw_20240130172749_46312.zip", # fallback mirror
        "size": 23539837,
        "crc32": 0x978d2100,
        "filename": "miband7_nfc_2.2.0.1.zip"
    },
    "2.0.0.2-std": {
        "version": "2.0.0.2",
        "type": "Standard (M2129B1)",
        "url": "https://cdn.cnbj2.fds.api.mi-img.com/hm-artifact-plat/firmware/20230718/1689667798367/fw_20230718160958_40578.zip",
        "size": 22340000,
        "crc32": None,
        "filename": "miband7_std_2.0.0.2.zip"
    }
}

class FirmwareDownloader:
    @staticmethod
    def list_available():
        return OFFICIAL_FIRMWARES

    @staticmethod
    def download(target_key: str, dest_dir: str = "./firmware") -> str:
        if target_key not in OFFICIAL_FIRMWARES:
            raise ValueError(f"Unknown firmware key '{target_key}'. Available: {list(OFFICIAL_FIRMWARES.keys())}")

        fw = OFFICIAL_FIRMWARES[target_key]
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, fw["filename"])

        if os.path.exists(dest_path):
            with open(dest_path, "rb") as f:
                cur_crc = zlib.crc32(f.read()) & 0xffffffff
            if fw["crc32"] is None or cur_crc == fw["crc32"]:
                print(f"[+] Firmware already cached: {dest_path}")
                return dest_path

        print(f"[*] Downloading official firmware {fw['version']} ({fw['type']})...")
        print(f"    CDN Source: {fw['url']}")
        
        resp = requests.get(fw["url"], stream=True, timeout=30)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\r    Progress: {downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB ({pct:.1f}%)", end="", flush=True)

        print()
        # Verify CRC
        with open(dest_path, "rb") as f:
            calc_crc = zlib.crc32(f.read()) & 0xffffffff
        if fw["crc32"] is not None and calc_crc != fw["crc32"]:
            raise RuntimeError(f"CRC32 mismatch! Expected 0x{fw['crc32']:08x}, got 0x{calc_crc:08x}")

        print(f"[+] Download verified successfully: 0x{calc_crc:08x} -> {dest_path}")
        return dest_path
