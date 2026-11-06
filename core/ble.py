import time
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from typing import Dict, Optional, Tuple, Callable

UUID_SERVICE_DFU = "00001530-0000-3512-2118-0009af100700"
UUID_CHAR_16 = "00000016-0000-3512-2118-0009af100700"
UUID_CHAR_17 = "00000017-0000-3512-2118-0009af100700"
UUID_CHAR_1531 = "00001531-0000-3512-2118-0009af100700"
UUID_CHAR_1532 = "00001532-0000-3512-2118-0009af100700"

UUID_CHAR_VER = "00002a28-0000-1000-8000-00805f9b34fb"
UUID_CHAR_BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
UUID_CHAR_SERIAL = "00002a25-0000-1000-8000-00805f9b34fb"

class BLEConnectionManager:
    def __init__(self, mac: str, adapter_path: str = "/org/bluez/hci0"):
        self.mac = mac.upper()
        self.dev_path = f"{adapter_path}/dev_{self.mac.replace(':', '_')}"
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.adapter = dbus.Interface(self.bus.get_object("org.bluez", adapter_path), "org.bluez.Adapter1")
        self.om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        
        self.chars = {}

    def discover_and_trust(self, timeout_sec: int = 5):
        objects = self.om.GetManagedObjects()
        if self.dev_path not in objects:
            print(f"[*] Discovering BLE devices to locate {self.mac}...")
            self.adapter.SetDiscoveryFilter({"Transport": "le", "DuplicateData": dbus.Boolean(True)})
            self.adapter.StartDiscovery()
            for _ in range(timeout_sec * 2):
                time.sleep(0.5)
                if self.dev_path in self.om.GetManagedObjects():
                    break
            self.adapter.StopDiscovery()

        if self.dev_path in self.om.GetManagedObjects():
            props = dbus.Interface(self.bus.get_object("org.bluez", self.dev_path), "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))

    def connect(self, timeout_sec: int = 15):
        self.discover_and_trust()
        dev_obj = self.bus.get_object("org.bluez", self.dev_path)
        dev = dbus.Interface(dev_obj, "org.bluez.Device1")
        props = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
        
        print(f"[*] Connecting to {self.mac}...")
        try:
            dev.Connect()
        except Exception as e:
            err_str = str(e)
            if "AlreadyConnected" not in err_str and "InProgress" not in err_str:
                raise e

        for _ in range(timeout_sec * 2):
            if props.Get("org.bluez.Device1", "ServicesResolved"):
                break
            time.sleep(0.5)

        self._map_characteristics()

    def disconnect(self):
        try:
            dev = dbus.Interface(self.bus.get_object("org.bluez", self.dev_path), "org.bluez.Device1")
            dev.Disconnect()
        except Exception:
            pass

    def _map_characteristics(self):
        objects = self.om.GetManagedObjects()
        for path, ifaces in objects.items():
            if path.startswith(self.dev_path) and "org.bluez.GattCharacteristic1" in ifaces:
                uuid = ifaces["org.bluez.GattCharacteristic1"].get("UUID", "").lower()
                c_obj = dbus.Interface(self.bus.get_object("org.bluez", path), "org.bluez.GattCharacteristic1")
                self.chars[uuid] = (c_obj, path)

    def get_char(self, uuid: str):
        uuid_lower = uuid.lower()
        if uuid_lower in self.chars:
            return self.chars[uuid_lower][0]
        # Partial match
        for k, v in self.chars.items():
            if uuid_lower in k:
                return v[0]
        return None

    def get_char_path(self, uuid: str):
        uuid_lower = uuid.lower()
        for k, v in self.chars.items():
            if uuid_lower in k:
                return v[1]
        return None

    def read_device_diagnostics(self) -> Dict[str, str]:
        diag = {}
        for name, uuid in [("firmware", UUID_CHAR_VER), ("battery", UUID_CHAR_BATTERY), ("serial", UUID_CHAR_SERIAL)]:
            c = self.get_char(uuid)
            if c:
                try:
                    val = bytes(c.ReadValue({}))
                    if name == "battery":
                        diag[name] = f"{int(val[0])}%"
                    else:
                        diag[name] = val.decode("utf-8", errors="ignore").strip()
                except Exception:
                    diag[name] = "N/A"
        return diag
