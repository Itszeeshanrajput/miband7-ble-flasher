# Troubleshooting & Error Codes Reference

This guide covers common issues and exact resolution steps when flashing the Xiaomi Smart Band 7 over Bluetooth Low Energy.

---

## 1. DFU Status Rejection Codes

During opcode negotiation (`0xd2` manifest or `0xd3` transfer start), the band's firmware update engine may return an error status byte:

### Error `0x03` — Authentication Required
- **Cause:** The band received a DFU manifest without prior cryptographic session authentication on Characteristics `0x0016` / `0x0017`.
- **Fix:** Ensure your 16-byte Auth Key is correct and that the ECDH B-163 handshake completed before calling `0xd2`.

### Error `0x22` — Battery Voltage Low (< 20%)
- **Cause:** The Zepp OS bootloader requires a minimum safety threshold of **20% battery charge** before allowing partition flashing. This prevents accidental power loss during NOR/NAND Flash erase operations.
- **Fix:** Place the band on its magnetic charging cable and let it charge to at least 30% before retrying.

### Error `0x47` — Insufficient Storage Space
- **Cause:** The internal NAND Flash partition does not have enough free sectors to unpack the incoming firmware bundle.
- **Fix:** In Zepp Life / Mi Fitness (or via Gadgetbridge), remove unused third-party watchfaces or large custom watchapps to free up storage.

---

## 2. Authentication Rejection Codes

During the ECDH handshake on Characteristic `0x0016` (Opcode `0x05`), the band returns a verification status:

### Code `0x25` — Authentication Failed / Wrong Key
- **Cause:** The 16-byte Auth Key supplied does not match the device's currently bonded secret key stored in its Secure NVRAM.
- **Fix:** Re-extract your Auth Key using Option `[2]` in `flasher.py`. If you recently paired the band with a new phone or account, the previous key was invalidated and regenerated.

### Code `0x26` — Invalid Handshake Math / Curve Mismatch
- **Cause:** The ECDH public key or shared secret point was incorrectly computed or malformed during the B-163 curve multiplication.
- **Fix:** Ensure Java (`openjdk-17-jdk` or `default-jdk`) is available and `AuthHelper.class` is compiled.

---

## 3. Bluetooth Connection & Host Environment

### Device Not Found / Discovery Timeout
- **Symptom:** `flasher.py` reports `device not found` or times out connecting.
- **Checks:**
  1. Ensure your Linux Bluetooth service is active:
     ```bash
     sudo systemctl start bluetooth
     sudo hciconfig hci0 up
     ```
  2. Ensure the Mi Band 7 is close to the computer (< 2 meters) and not currently bonded/connected in an exclusive link to a smartphone.
  3. Turn off Bluetooth on your smartphone temporarily to ensure the band broadcasts advertising beacons to the PC.

### BlueZ D-Bus Permission Denied
- **Symptom:** `dbus.exceptions.DBusException: org.bluez.Error.NotPermitted`.
- **Fix:** Add your user to the `bluetooth` group or run the script with appropriate privileges:
  ```bash
  sudo usermod -aG bluetooth $USER
  ```
