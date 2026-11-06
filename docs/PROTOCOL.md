# BLE GATT Services & Zepp OS DFU Protocol Specification

This document provides the byte-level reference for the Bluetooth Low Energy (BLE) GATT profile and DFU update protocol used on the **Xiaomi Smart Band 7**.

---

## 1. GATT Attribute Table

| Service UUID | Characteristic UUID | Handle | Name | Properties | Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0000fee0` | `00000016-0000-3512-2118-0009af100700` | `0x0016` | Chunked Write | `Write without response` | Sends chunked authentication frames & configs |
| `0000fee0` | `00000017-0000-3512-2118-0009af100700` | `0x0017` | Chunked Read | `Notify`, `Write without resp` | Receives band challenges & sends chunk ACKs |
| `00001530` | `00001531-0000-3512-2118-0009af100700` | `0x1531` | DFU Control | `Write`, `Notify` | DFU command opcodes (`0xd0`-`0xd6`) |
| `00001530` | `00001532-0000-3512-2118-0009af100700` | `0x1532` | DFU Data | `Write without response` | Streams firmware raw binary packets |
| `0000180a` | `00002a28-0000-1000-8000-00805f9b34fb` | `0x2a28` | Software Revision | `Read` | Returns active firmware version string |
| `0000180f` | `00002a19-0000-1000-8000-00805f9b34fb` | `0x2a19` | Battery Level | `Read`, `Notify` | Returns 1-byte battery percentage |

---

## 2. DFU Protocol Opcodes (`0x1531`)

| Opcode | Hex | Direction | Description | Response / Payload |
| :--- | :--- | :--- | :--- | :--- |
| `CMD_REQUEST_PARAMS` | `0xd0` | Host -> Band | Requests chunk and buffer limits | `[0x10, 0xd0, 0x01, 0x05, 0x00, 0x20]` (`8192` bytes) |
| `CMD_SEND_FW_INFO` | `0xd2` | Host -> Band | Sends 19-byte firmware manifest | `[0x10, 0xd2, status]` (`0x01` = Success) |
| `CMD_START_TRANSFER`| `0xd3` | Host -> Band | Initiates byte transmission | `[0xd3, 0x01]` -> `[0x10, 0xd3, 0x01]` |
| `REPLY_PROGRESS` | `0xd4` | Band -> Host | Acknowledges received chunk | `[0x10, 0xd4, offset_4B_LE]` |
| `CMD_COMPLETE_XFER` | `0xd5` | Host -> Band | Signals end of file transmission | `[0xd5]` -> `[0x10, 0xd5, 0x01]` |
| `CMD_FINALIZE` | `0xd6` | Host -> Band | Instructs bootloader to reboot & apply | `[0xd6]` -> `[0x10, 0xd6, 0x01]` |

---

## 3. 19-Byte Firmware Manifest Structure (`0xd2`)

When initiating an update, the host transmits a 19-byte structured buffer to Characteristic `0x1531`:

```
Byte Offset | Length | Field Name         | Format    | Example / Description
------------+--------+--------------------+-----------+--------------------------------------------
0           | 1 Byte | Opcode             | uint8     | 0xd2 (CMD_SEND_FW_INFO)
1           | 1 Byte | Firmware Type      | uint8     | 0x00 (FIRMWARE / UIHH Zip Package)
2 - 5       | 4 Byte | Package Size       | uint32 LE | Total length in bytes (e.g. 23,539,837)
6 - 9       | 4 Byte | CRC32 Checksum     | uint32 LE | Hardware CRC32 of complete .zip package
10 - 11     | 2 Byte | Chunk Size         | uint16 LE | Negotiated chunk buffer (8,192 bytes)
12          | 1 Byte | Update Mode        | uint8     | 0x00 (Foreground update screen)
13          | 1 Byte | Component Index    | uint8     | 0x00
14          | 1 Byte | Component Count    | uint8     | 0x01
15 - 18     | 4 Byte | Total Package Size | uint32 LE | Mirror of Package Size
```

---

## 4. Chunk Streaming to Data Characteristic (`0x1532`)

1. Each 8,192-byte chunk is sliced into packets matching `MTU - 3` (e.g., 244 bytes for standard BLE 4.2/5.0 MTU of 247).
2. Packets are written rapidly to `0x1532` using `write-without-response`.
3. After transmitting the 8,192 bytes, the host awaits notification `[0x10, 0xd4, offset]` on `0x1531`.
4. When `offset >= total_size`, opcode `0xd5` signals completion.
