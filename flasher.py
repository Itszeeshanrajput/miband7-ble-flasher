#!/usr/bin/env python3
"""
===================================================================================
 Xiaomi Smart Band 7 (Zepp OS / Renesas DA14706) Standalone BLE Firmware Flasher
 Directly flashes official firmware over Bluetooth Low Energy from Linux PC.
 Zero smartphone or third-party cloud apps required.
===================================================================================
"""

import sys
import os
import time
import argparse
import json
from gi.repository import GLib

from core.auth import ECDHAuthEngine
from core.ble import BLEConnectionManager, UUID_CHAR_17, UUID_CHAR_1531
from core.dfu import ZeppOSDFUEngine
from core.downloader import FirmwareDownloader
from core.token import AuthKeyExtractor

CONFIG_FILE = "config.json"

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║        Xiaomi Smart Band 7 (Mi Band 7) Standalone BLE Flasher        ║
║   ECDH B-163 Cryptographic Auth & Zepp OS Over-The-Air DFU Engine     ║
╚══════════════════════════════════════════════════════════════════════╝
""")

def print_progress_bar(offset: int, total_size: int, start_time: float):
    now = time.time()
    elapsed = max(now - start_time, 0.001)
    pct = (offset / total_size) * 100
    avg_speed = (offset / elapsed / 1024)
    remaining_bytes = total_size - offset
    eta = (remaining_bytes / (avg_speed * 1024)) if avg_speed > 0 else 0
    eta_min = int(eta // 60)
    eta_sec = int(eta % 60)
    
    bar_len = 30
    filled = int(bar_len * (offset / total_size))
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r[{bar}] {pct:5.1f}% | {offset/(1024*1024):.2f}/{total_size/(1024*1024):.2f} MB | {avg_speed:5.1f} KB/s | ETA: {eta_min:02d}m{eta_sec:02d}s", end="", flush=True)

class BandFlasherApp:
    def __init__(self, mac: str, auth_key: str, fw_path: str):
        self.mac = mac.upper()
        self.auth_key = auth_key
        self.fw_path = fw_path
        
        self.ble = BLEConnectionManager(self.mac)
        self.auth = ECDHAuthEngine(self.auth_key)
        self.loop = GLib.MainLoop()
        
        self.c16 = None
        self.c17 = None
        self.c1531 = None
        self.c1532 = None
        self.dfu = None
        
        self.write_handle = 1
        self.reassembly_buffer = bytearray()
        self.expected_length = 0
        self.current_type = 0

    def send_auth_chunk(self, type_id: int, data: bytes):
        length = len(data)
        flags = 0x07  # first | last | needs ack
        header = bytearray([
            0x03, flags, 0x00, self.write_handle, 0x00,
            length & 0xff, (length >> 8) & 0xff, (length >> 16) & 0xff, (length >> 24) & 0xff,
            type_id & 0xff, (type_id >> 8) & 0xff
        ])
        self.write_handle += 1
        packet = header + data
        self.c16.WriteValue(list(packet), {})

    def on_c17_notify(self, iface, changed, invalidated):
        if "Value" not in changed:
            return
        val = bytes(changed["Value"])
        if len(val) < 2 or val[0] != 0x03:
            return
            
        flags = val[1]
        is_first = bool(flags & 0x01)
        is_last = bool(flags & 0x02)
        needs_ack = bool(flags & 0x04)
        
        handle = val[3]
        count = val[4]
        idx = 5
        
        if is_first:
            self.expected_length = val[idx] | (val[idx+1] << 8) | (val[idx+2] << 16) | (val[idx+3] << 24)
            self.current_type = val[idx+4] | (val[idx+5] << 8)
            idx += 6
            self.reassembly_buffer = bytearray()
            
        self.reassembly_buffer.extend(val[idx:])
        
        if needs_ack:
            ack = [0x04, 0x00, handle, 0x01, count]
            self.c17.WriteValue(ack, {})
            
        if is_last:
            payload = bytes(self.reassembly_buffer)
            self.handle_auth_payload(self.current_type, payload)

    def handle_auth_payload(self, type_id: int, payload: bytes):
        if type_id != 0x0082:
            return
            
        if len(payload) >= 3 and payload[0] == 0x10 and payload[1] == 0x04 and payload[2] == 0x01:
            print("[+] Received band challenge + remote ECDH public key.")
            remote_random = payload[3:19]
            remote_public = payload[19:67]
            
            command = self.auth.compute_challenge_response(remote_public, remote_random)
            print("[+] Derived session key. Sending challenge response...")
            self.send_auth_chunk(0x0082, command)
            
        elif len(payload) >= 3 and payload[0] == 0x10 and payload[1] == 0x05:
            status = payload[2]
            if status == 0x01:
                print("\n" + "="*60)
                print("🔒 AUTHENTICATION CONFIRMED: Hardware session unlocked!")
                print("="*60 + "\n")
                self.dfu.start()
            else:
                print(f"[-] Authentication rejected: Status code 0x{status:02x}")
                self.loop.quit()

    def run(self):
        print(f"[*] Reading firmware payload: {self.fw_path}...")
        with open(self.fw_path, "rb") as f:
            fw_data = f.read()
            
        public_ec = self.auth.generate_public_key()
        self.ble.connect()
        
        self.c16 = self.ble.get_char("0016")
        self.c17 = self.ble.get_char("0017")
        self.c1531 = self.ble.get_char("1531")
        self.c1532 = self.ble.get_char("1532")
        
        if not all([self.c16, self.c17, self.c1531, self.c1532]):
            raise RuntimeError("Required DFU GATT characteristics not found on device!")

        # Initialize DFU Engine
        self.dfu = ZeppOSDFUEngine(
            self.c1531,
            self.c1532,
            fw_data,
            self.loop,
            progress_callback=print_progress_bar
        )

        # Hook D-Bus signal receivers
        self.ble.bus.add_signal_receiver(
            self.on_c17_notify,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            path=self.ble.get_char_path("0017")
        )
        self.c17.StartNotify()

        self.ble.bus.add_signal_receiver(
            lambda iface, changed, inv: self.dfu.handle_notification(bytes(changed["Value"])) if "Value" in changed else None,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            path=self.ble.get_char_path("1531")
        )
        self.c1531.StartNotify()

        time.sleep(0.5)
        print("[*] Initiating 2021 ECDH B-163 handshake...")
        pub_cmd = bytes([0x04, 0x02, 0x00, 0x02]) + bytes(public_ec)
        self.send_auth_chunk(0x0082, pub_cmd)

        self.loop.run()
        self.ble.disconnect()

def interactive_wizard():
    print_banner()
    cfg = load_config()
    
    print("Select an option:")
    print("  [1] 🚀 Auto-Flash Firmware (Full Pipeline)")
    print("  [2] 🔑 Extract Auth Key from Xiaomi Account")
    print("  [3] 📥 Download Official Firmware Package")
    print("  [4] 🔍 Scan & Diagnose Device")
    print("  [5] 🚪 Exit")
    
    choice = input("\nEnter choice [1-5]: ").strip()
    
    if choice == "1":
        mac = input(f"Enter Band Bluetooth MAC [{cfg.get('mac', 'E8:3F:50:64:CB:CB')}]: ").strip() or cfg.get('mac', 'E8:3F:50:64:CB:CB')
        key = input(f"Enter 16-byte Auth Key [{cfg.get('auth_key', '')}]: ").strip() or cfg.get('auth_key', '')
        if not key:
            print("[-] Auth key is required! Run option [2] to extract it first.")
            return

        fw_choice = input("Select firmware: [1] 2.2.0.1 Std (Latest), [2] Local file: ").strip()
        if fw_choice == "2":
            fw_path = input("Enter path to firmware .zip: ").strip()
        else:
            fw_path = FirmwareDownloader.download("2.2.0.1-std")

        cfg["mac"] = mac
        cfg["auth_key"] = key
        save_config(cfg)

        app = BandFlasherApp(mac, key, fw_path)
        app.run()

    elif choice == "2":
        print("\n[*] Xiaomi Account Auth Key Extractor")
        print("1. Click the following URL (or we will open it in your browser):")
        print(f"👉 {AuthKeyExtractor.get_login_url()}\n")
        AuthKeyExtractor.open_browser()
        print("2. Sign in with your Xiaomi/Google account that is paired with your band.")
        print("3. You will be redirected to an empty or failed page (e.g., https://hm.xiaomi.com/watch.do?code=...)")
        redirect_url = input("\nPaste the FULL redirect URL here: ").strip()
        try:
            devices = AuthKeyExtractor.extract_from_redirect_url(redirect_url)
            print("\nFound registered devices:")
            for d in devices:
                print(f"  MAC: {d['mac']} | Auth Key: {d['auth_key']}")
                if d['auth_key']:
                    cfg['mac'] = d['mac']
                    cfg['auth_key'] = d['auth_key']
                    save_config(cfg)
                    print(f"[+] Saved Auth Key for {d['mac']} to {CONFIG_FILE}!")
        except Exception as e:
            print(f"[-] Extraction error: {e}")

    elif choice == "3":
        print("\nAvailable official firmwares:")
        fws = FirmwareDownloader.list_available()
        keys = list(fws.keys())
        for i, k in enumerate(keys):
            print(f"  [{i+1}] {fws[k]['version']} - {fws[k]['type']}")
        idx = int(input("\nEnter choice: ").strip()) - 1
        FirmwareDownloader.download(keys[idx])

    elif choice == "4":
        mac = input(f"Enter MAC [{cfg.get('mac', 'E8:3F:50:64:CB:CB')}]: ").strip() or cfg.get('mac', 'E8:3F:50:64:CB:CB')
        ble = BLEConnectionManager(mac)
        ble.connect()
        diag = ble.read_device_diagnostics()
        print("\nDevice Diagnostics:")
        for k, v in diag.items():
            print(f"  {k.capitalize():15}: {v}")
        ble.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Xiaomi Smart Band 7 BLE Firmware Flasher")
    parser.add_argument("--mac", help="Band Bluetooth MAC address")
    parser.add_argument("--auth-key", help="16-byte hex Auth Key")
    parser.add_argument("--file", help="Path to firmware ZIP file")
    parser.add_argument("--auto", action="store_true", help="Run without interactive prompts")
    args = parser.parse_args()

    if args.auto or (args.mac and args.auth_key and args.file):
        if not args.mac or not args.auth_key or not args.file:
            print("[-] For automated mode, --mac, --auth-key, and --file must all be supplied.")
            sys.exit(1)
        app = BandFlasherApp(args.mac, args.auth_key, args.file)
        app.run()
    else:
        interactive_wizard()

if __name__ == "__main__":
    main()
