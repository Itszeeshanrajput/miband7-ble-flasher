# ⚡ Xiaomi Smart Band 7 Standalone BLE Firmware Flasher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20%7C%20BlueZ-green.svg)](https://www.bluez.org/)
[![Hardware: Renesas DA14706](https://img.shields.io/badge/SoC-Renesas%20DA14706-orange.svg)](https://www.renesas.com/)
[![OS: Zepp OS](https://img.shields.io/badge/OS-Zepp%20OS%201.0-purple.svg)](https://docs.zepp.com/)

A fully automated, educational, and user-friendly tool to flash official and custom firmware to the **Xiaomi Smart Band 7** (`M2129B1` / `M2130B1` NFC) directly over **Bluetooth Low Energy (BLE)** from a Linux PC — **no smartphone, Zepp Life, or Mi Fitness app required.**

---

## 🌟 Why This Project?

Official smartphone companion apps enforce region checks, staged rollouts, and prevent direct firmware sideloading or downgrades. This tool gives you full control over your hardware by implementing the raw **Zepp OS Over-The-Air (DFU) protocol** and **NIST B-163 Elliptic Curve Cryptography** directly against the band's Bluetooth stack.

### Key Features:
- 🚀 **1-Click Interactive Wizard:** Easy step-by-step guidance for beginners.
- 🤖 **Full Automation Mode:** Complete headless flashing for automated pipelines and scripts.
- 🔑 **Built-in Auth Key Extractor:** Securely retrieves your 16-byte pairing token from your Xiaomi / Google account.
- 📥 **Direct CDN Downloader:** Automatically downloads verified official firmware packages (`v2.2.0.1`, `v2.0.0.2`) from Xiaomi servers with CRC32 verification.
- 🔒 **Hardware Cryptography:** Implements the modern 2021+ ECDH B-163 curve handshake and AES-128 challenge-response required by the Renesas DA14706 SoC.
- 📊 **Real-Time Progress & Telemetry:** Dynamic live transfer bar with speed metrics (KB/s), elapsed time, and ETA.
- 🩺 **Hardware Diagnostics:** Queries battery voltage, hardware revision, serial number, and active firmware version.

---

## 🏗️ How It Works (Protocol Architecture)

```mermaid
sequenceDiagram
    autonumber
    participant Host as Linux PC (Flasher)
    participant Band as Mi Band 7 (DA14706)

    Note over Host,Band: 1. Cryptographic Handshake (0xfee0)
    Host->>Band: 0x0016: Send Public Key (48B ECDH B-163 point)
    Band-->>Host: 0x0017: Return Nonce Challenge (16B) + Band Public Key (48B)
    Note over Host: Derive Shared Secret on B-163:<br/>Session_Key = Shared_EC ^ Auth_Key<br/>Encrypt Challenge with Auth_Key & Session_Key
    Host->>Band: 0x0016: Send Double-Encrypted Challenge (33B)
    Band-->>Host: 0x0017: Return 0x10 0x05 0x01 (AUTH SUCCESS)

    Note over Host,Band: 2. DFU Negotiation (0x1530)
    Host->>Band: 0x1531: Request Parameters (0xd0)
    Band-->>Host: 0x1531: Return Chunk Size (8,192 Bytes)
    Host->>Band: 0x1531: Send 19-Byte Manifest (0xd2: Size, CRC32, Chunk)
    Band-->>Host: 0x1531: Return 0x10 0xd2 0x01 (MANIFEST ACCEPTED)

    Note over Host,Band: 3. Streaming & Partition Flashing
    Host->>Band: 0x1531: Trigger Transfer Start (0xd3 0x01)
    loop Every 8,192 Byte Chunk
        Host->>Band: 0x1532: Stream 244-byte MTU packets (write-without-response)
        Band-->>Host: 0x1531: Progress Notification (0xd4 with Byte Offset)
    end
    Host->>Band: 0x1531: Complete Transfer (0xd5)
    Band-->>Host: 0x1531: Acknowledge Integrity (0x10 0xd5 0x01)
    Host->>Band: 0x1531: Finalize & Reboot (0xd6)
    Note over Band: Band writes NOR/NAND Flash partitions and reboots into new firmware!
```

---

## ⚡ Quick Start (Beginner Friendly)

### 1. Install Prerequisites
On Debian / Ubuntu / Kali / Raspberry Pi OS:
```bash
sudo apt update
sudo apt install -y bluez python3-dbus python3-gi default-jdk python3-pip git
sudo systemctl start bluetooth
```

### 2. Clone the Repository
```bash
git clone https://github.com/Itszeeshanrajput/miband7-ble-flasher.git
cd miband7-ble-flasher
pip3 install -r requirements.txt
```

### 3. Launch the Interactive Flasher
```bash
python3 flasher.py
```

The tool will display an interactive menu:
```text
╔══════════════════════════════════════════════════════════════════════╗
║        Xiaomi Smart Band 7 (Mi Band 7) Standalone BLE Flasher        ║
║   ECDH B-163 Cryptographic Auth & Zepp OS Over-The-Air DFU Engine     ║
╚══════════════════════════════════════════════════════════════════════╝

Select an option:
  [1] 🚀 Auto-Flash Firmware (Full Pipeline)
  [2] 🔑 Extract Auth Key from Xiaomi Account
  [3] 📥 Download Official Firmware Package
  [4] 🔍 Scan & Diagnose Device
  [5] 🚪 Exit
```

---

## 🤖 Automated Headless Mode (Power Users & CI)

If you already know your band's Bluetooth MAC address, Auth Key, and have the firmware file:

```bash
python3 flasher.py \
  --mac E8:3F:50:64:CB:CB \
  --auth-key a83d54bf0287bec3a74c436dcb75f4cd \
  --file ./firmware/miband7_std_2.2.0.1.zip \
  --auto
```

---

## 🔑 How to Get Your 16-Byte Auth Key

Every modern Xiaomi / Huami wearable requires a **16-byte cryptographic secret** (Auth Key) to unlock its Bluetooth GATT services.

1. In `flasher.py`, select **Option `[2]`**.
2. It will open Xiaomi's official OAuth authorization page in your browser.
3. Log in with the Xiaomi / Google account that is paired to your Mi Band 7.
4. After logging in, you will be redirected to a URL starting with:
   `https://hm.xiaomi.com/watch.do?code=...`
5. Copy and paste that full redirect URL into the prompt.
6. The tool automatically exchanges the token and prints your band's 16-byte Auth Key, saving it to `config.json` for future sessions!

---

## 📦 Supported Official Firmware Packages

| Version | Device Model | Codename | Package Size | Hardware CRC32 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`v2.2.0.1`** | Standard (`M2129B1`) | `hmpace.watch.v7` | 22.45 MB | `0x978d2100` | ✅ Verified Stable |
| **`v2.2.0.1`** | NFC (`M2130B1`) | `hmpace.watch.v7nfc` | 22.45 MB | `0x978d2100` | ✅ Verified Stable |
| **`v2.0.0.2`** | Standard (`M2129B1`) | `hmpace.watch.v7` | 21.30 MB | — | ✅ Verified Stable |

---

## 📚 Deep-Dive Documentation

For engineers, security researchers, and developers wanting to understand the inner workings:
- [Hardware Architecture & Memory Layout](docs/ARCHITECTURE.md) — Renesas DA14706 SoC, Dual NOR/NAND Flash, and Zepp OS 1.0 subsystem.
- [BLE GATT Services & Protocol Reference](docs/PROTOCOL.md) — Byte offsets, 19-byte manifest structure, and packet fragmentation.
- [Troubleshooting & Error Codes](docs/TROUBLESHOOTING.md) — Explanations for errors `0x03`, `0x22`, `0x25`, `0x26`, and `0x47`.

---

## ⚠️ Safety Guidelines & Best Practices

- **Battery Voltage:** Always ensure your band has **at least 30% battery** before flashing. The bootloader rejects updates below 20% (Error `0x22`) to prevent accidental power loss during Flash sector writes.
- **Proximity:** Keep the band within **1 meter** of your computer during the transfer.
- **Charging Cable:** Placing the band on its magnetic charging cable during flashing is recommended.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
Built for educational, research, and device interoperability purposes.
