import time
import struct
import zlib
from typing import Callable, Optional
from gi.repository import GLib

CMD_REQUEST_PARAMS = 0xd0
CMD_SEND_FW_INFO = 0xd2
CMD_START_TRANSFER = 0xd3
REPLY_PROGRESS = 0xd4
CMD_COMPLETE_TRANSFER = 0xd5
CMD_FINALIZE_UPDATE = 0xd6

class ZeppOSDFUEngine:
    def __init__(self, c1531, c1532, fw_data: bytes, loop: GLib.MainLoop, progress_callback: Optional[Callable] = None):
        self.c1531 = c1531
        self.c1532 = c1532
        self.fw_data = fw_data
        self.total_size = len(fw_data)
        self.crc32 = zlib.crc32(fw_data) & 0xffffffff
        self.loop = loop
        self.progress_callback = progress_callback
        
        self.chunk_size = 8192
        self.packet_size = 244
        self.start_time = 0
        self.last_time = 0
        self.last_offset = 0

    def start(self):
        print("[*] Requesting DFU parameters (0xd0)...")
        self.c1531.WriteValue([CMD_REQUEST_PARAMS], {})

    def send_manifest(self):
        print(f"[*] Submitting firmware manifest (Size: {self.total_size:,} B, CRC32: 0x{self.crc32:08x})...")
        size_b = struct.pack("<I", self.total_size)
        crc_b = struct.pack("<I", self.crc32)
        chunk_b = struct.pack("<H", self.chunk_size)
        manifest = [CMD_SEND_FW_INFO, 0] + list(size_b) + list(crc_b) + list(chunk_b) + [0, 0, 1] + list(size_b)
        self.c1531.WriteValue(manifest, {})

    def send_data_chunk(self, offset: int):
        if offset >= self.total_size:
            print("\n[*] Upload finished. Finalizing transfer (0xd5)...")
            self.c1531.WriteValue([CMD_COMPLETE_TRANSFER], {})
            return

        remaining = self.total_size - offset
        chunk_len = min(remaining, self.chunk_size)
        chunk_bytes = self.fw_data[offset : offset + chunk_len]
        
        packets = (chunk_len + self.packet_size - 1) // self.packet_size
        for i in range(packets):
            packet = chunk_bytes[i * self.packet_size : (i + 1) * self.packet_size]
            self.c1532.WriteValue(list(packet), {})

    def handle_notification(self, val: bytes):
        if len(val) < 3 or val[0] != 0x10:
            return

        cmd = val[1]
        status = val[2]

        if cmd == CMD_REQUEST_PARAMS and status == 1:
            self.chunk_size = val[4] | (val[5] << 8)
            print(f"[+] DFU parameters negotiated: chunk length = {self.chunk_size} bytes")
            self.send_manifest()

        elif cmd == CMD_SEND_FW_INFO:
            if status == 1:
                print("[+] Manifest verified by band hardware. Initiating transmission (0xd3)...")
                self.c1531.WriteValue([CMD_START_TRANSFER, 0x01], {})
            else:
                err_msg = {
                    0x03: "Authentication required",
                    0x22: "Battery too low (< 20%)",
                    0x47: "Insufficient flash storage space"
                }.get(status, f"Unknown rejection code 0x{status:02x}")
                print(f"[-] Manifest rejected: {err_msg}")
                self.loop.quit()

        elif cmd == CMD_START_TRANSFER:
            if status == 1:
                print("[+] Transfer started! Streaming first chunk...")
                self.start_time = time.time()
                self.last_time = self.start_time
                self.last_offset = 0
                self.send_data_chunk(0)
            else:
                print(f"[-] Transfer start rejected: 0x{status:02x}")
                self.loop.quit()

        elif cmd == REPLY_PROGRESS:
            if len(val) >= 6:
                offset = val[2] | (val[3] << 8) | (val[4] << 16) | (val[5] << 24)
                if self.progress_callback:
                    self.progress_callback(offset, self.total_size, self.start_time)
                self.send_data_chunk(offset)

        elif cmd == CMD_COMPLETE_TRANSFER:
            if status == 1:
                print("\n[+] Integrity verified! Finalizing firmware installation (0xd6)...")
                self.c1531.WriteValue([CMD_FINALIZE_UPDATE], {})
            else:
                print(f"[-] Complete transfer rejected: 0x{status:02x}")
                self.loop.quit()

        elif cmd == CMD_FINALIZE_UPDATE:
            print("\n" + "="*65)
            print("🎉 FIRMWARE UPGRADE FINALIZED! The band is applying updates and rebooting.")
            print("="*65 + "\n")
            self.loop.quit()
