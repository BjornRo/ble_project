import _thread
import time

import bluetooth
import ujson
import uos
import utils
from ucollections import namedtuple

REMOTE_FILE = "remote"
SETTINGS_FILE = "settings"


def write_settings(setting: str, cfg: dict[str, list[float]]):
    with open(SETTINGS_FILE, "wt") as f:
        f.write(f"{current_setting}\n")
        f.write(ujson.dumps(cfg))


try:
    with open(SETTINGS_FILE, "rt") as f:
        current_setting: str = f.readline().rstrip()
        settings_cfg: dict[str, list[float]] = ujson.load(f)
except:
    with open(SETTINGS_FILE, "wt") as f:
        current_setting = "default"
        settings_cfg = dict(default=[0.0, 0.25, 0.5, 0.75, 1.0])
        write_settings(current_setting, settings_cfg)
setting_index = 0  # Start from lowest


# PAIRING_SERVICE_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-C70B7CA38A70")
PAIRING_CHAR_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-C70B7CA38A71")

ConnHandle = int
ValueHandle = int
StartHandle = int
EndHandle = int
AddrType = int  # Mac: 0 = Public, 1 = Random
AdvertiseType = int  # advertisement event type
DefHandle = int  # handle of the characteristic declaration

SERVICE_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-C70B7CA38A72")
JSON_DATA_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-C70B7CA38A73")
SETTING_DATA_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-C70B7CA38A74")

SERVICES = (
    SERVICE_UUID,
    (JSON_DATA_UUID, utils.FLAG_WRITE | utils.FLAG_READ),
    (SETTING_DATA_UUID, utils.FLAG_WRITE | utils.FLAG_READ),
)


class RemoteHandler:
    def __init__(self, ble: bluetooth.BLE):
        self.connection: ConnHandle = -1
        self.ble = ble
        self._default_key = b"\xca\xfe\x13\x37"
        try:
            with open(REMOTE_FILE, "rb") as f:
                self.remote_key = f.read()
        except:
            self.remote_key = self._default_key

    def run(self):
        self.ble.gap_scan(0, 100_000, 100_000)

    def handle_request(self, event: int, data: tuple):
        if event == utils.IRQ_SCAN_RESULT:
            self.pair_remote(data)
        elif event == utils.IRQ_PERIPHERAL_CONNECT:
            self.connect_remote(data)
        elif event == utils.IRQ_PERIPHERAL_DISCONNECT:
            self.connection = -1
        elif event == utils.IRQ_GATTC_CHARACTERISTIC_RESULT:
            self.handle_characteristic(data)
        elif event == utils.IRQ_GATTC_WRITE_DONE:
            self.handle_write_done(data)
        elif event == utils.IRQ_GATTC_NOTIFY:
            self.handle_notify(data)

    def pair_remote(self, data: tuple[AddrType, memoryview, AdvertiseType, int, memoryview]):
        addr_type, mac_addr, adv_type, rssi, adv_data = data
        if adv_type == 0x00:
            if self.remote_key != self._default_key:
                length, ad_type, *ad_data = adv_data
                if ad_type == 0xFF and length == len(self.remote_key) + 1 and bytes(ad_data) == self.remote_key:
                    if self.connection == -1:
                        self.ble.gap_connect(addr_type, mac_addr)
            elif adv_data[2:6] == self.remote_key and len(adv_data) == 6:
                if self.connection == -1:
                    self.ble.gap_connect(addr_type, mac_addr)

    def connect_remote(self, data: tuple[ConnHandle, AddrType, memoryview]):
        self.connection = data[0]
        self.ble.gattc_discover_characteristics(data[0], 1, 65535)

    def handle_characteristic(self, data: tuple[ConnHandle, DefHandle, ValueHandle, int, bluetooth.UUID]):
        conn_handle, def_handle, value_handle, properties, uuid = data
        if uuid == PAIRING_CHAR_UUID:
            new_key = utils.gen_64bits()
            self._pending_key = new_key
            self.ble.gattc_write(conn_handle, value_handle, new_key, 1)

    def handle_write_done(self, data: tuple[ConnHandle, ValueHandle, int]):
        if data[-1] == 0:  # 0 success, 1 fail
            self.remote_key = self._pending_key
            f = open(REMOTE_FILE, "wb")
            f.write(self.remote_key)
            f.flush()
        else:
            self.ble.gap_disconnect(data[0])
        del self._pending_key

    def handle_notify(self, data: tuple[ConnHandle, ValueHandle, bytes]):
        global setting_index
        if bool(data[-1]):
            setting_index = min(len(settings_cfg[current_setting]) - 1, setting_index + 1)
        else:
            setting_index = max(0, setting_index - 1)
        value = settings_cfg[current_setting][setting_index]


class PhoneHandler:
    def __init__(self, ble: bluetooth.BLE, name=b"MyProject"):
        self.connection: ConnHandle = -1
        self.ble = ble
        ((self.json_handle,),) = self.ble.gatts_register_services((SERVICES,))
        self.payload = utils.advertising_payload(name=name, services=[SERVICE_UUID])

    def handle_request(self, event: int, data: tuple):
        if event == utils.IRQ_CENTRAL_CONNECT:
            self.connection = data[0]
            self.advertise(None)
        elif event == utils.IRQ_CENTRAL_DISCONNECT:
            self.connection = -1
            self.advertise()
        elif event == utils.IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self.ble.gatts_read(value_handle)

    def advertise(self, interval_us: int | None = 100_000):
        self.ble.gap_advertise(interval_us, adv_data=self.payload)


class BLEHandler:
    def __init__(self, ble: bluetooth.BLE, remote: RemoteHandler, phone: PhoneHandler):
        self.ble = ble
        self.remote = remote
        self.phone = phone
        self.ble.gatts_register_services((SERVICES,))

    def run(self):
        self.ble.irq(self.event_handler)
        self.ble.active(True)
        self.remote.run()

    def event_handler(self, event: int, data: tuple):
        if data[0] == self.remote.connection:
            self.remote.handle_request(event, data)
        elif data[0] == self.phone.connection:
            self.phone.handle_request(event, data)


ble = bluetooth.BLE()
