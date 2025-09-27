import struct

import bluetooth
import ujson
import utime
from micropython import const

ble = bluetooth.BLE()


def advertising_payload(
    limited_disc=False,
    br_edr=False,
    name: str | None = None,
    services: list[bluetooth.UUID] | None = None,
    appearance=0,
):
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += struct.pack("BB", len(value) + 1, adv_type) + value

    _append(
        1,
        struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
    )
    if name:
        _append(9, name)
    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 2:
                _append(3, b)
            elif len(b) == 4:
                _append(5, b)
            elif len(b) == 16:
                _append(7, b)
    if appearance:
        _append(25, struct.pack("<h", appearance))
    if len(payload) > 31:
        raise ValueError("advertising payload too large")
    return payload


class AdvertisementHandler:
    def __init__(
        self,
        curr_setting: str,
        settings_config: dict[str, list[float]],
        cooldown_ms=200,
    ):
        self.settings_config = settings_config
        self.curr_setting = curr_setting  # Which settings to choose
        self.setting_index = 0  # Start from lowest
        self.remote_file = "stored_remote"
        self.cooldown_ms = cooldown_ms
        self.last_message = 0
        try:
            with open(self.remote_file, "rb") as f:
                self.remote_mac_addr = f.read()
        except:
            self.remote_mac_addr = None

    def increase_setting(self):
        self.setting_index = min(len(self.settings_config[self.curr_setting]) - 1, self.setting_index + 1)

    def decrease_setting(self):
        self.setting_index = max(0, self.setting_index - 1)

    def handle_event(self, data: tuple[int, memoryview, int, int, memoryview]):
        addr_type, mac_addr, adv_type, rssi, adv_data = data
        print(adv_data[2:6])
        if adv_data[2:6] == b"\xca\xfe\x12\x34" and len(adv_data) == 7:
            if self.remote_mac_addr is None:
                remote_mac_addr = bytes(mac_addr)
                f = open(self.remote_file, "wb")
                f.write(remote_mac_addr)
                f.flush()
                del f
            elif self.remote_mac_addr == mac_addr:
                now = utime.ticks_ms()
                if utime.ticks_diff(now, self.last_message) >= self.cooldown_ms:
                    self.last_message = now  # update last_message
                    print(bytes(adv_data))
                    self.increase_setting() if adv_data[6] == 2 else self.decrease_setting()
            else:
                print(self.remote_mac_addr == mac_addr)

    @staticmethod
    def load(settings_file="settings"):
        try:
            with open(settings_file, "rt") as f:
                __curr_setting = f.readline().rstrip()
                __settings_cfg = ujson.load(f)
                settings = AdvertisementHandler(__curr_setting, __settings_cfg)
        except:
            with open(settings_file, "wt") as f:
                settings = AdvertisementHandler("default", dict(default=[0.25, 0.5, 0.75, 1.0]))
                f.write(f"{settings.curr_setting}\n")
                f.write(ujson.dumps(settings.settings_config))
        return settings


class CharacteristicHandler:
    def __init__(self, ble: bluetooth.BLE):
        _FLAG_READ = 2
        _FLAG_WRITE_NO_RESPONSE = 4
        _FLAG_WRITE = 8
        _FLAG_NOTIFY = 16

        _UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        _UART_TX = (
            bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
            _FLAG_READ | _FLAG_NOTIFY,
        )
        _UART_RX = (
            bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
            _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
        )
        _UART_SERVICE = (
            _UART_UUID,
            (_UART_TX, _UART_RX),
        )
        self._connections = set()
        self._write_callback = None
        self._payload = advertising_payload(name="mpy-uart", services=[_UART_UUID])
        self.ble = ble
        ((self.handle_tx, self.handle_rx),) = self.ble.gatts_register_services((_UART_SERVICE,))

    def handle_event(self, event: int, data: tuple):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self.ble.gatts_read(value_handle)
            if value_handle == self.handle_rx and self._write_callback:
                self._write_callback(value)

    def send(self, data):
        for conn_handle in self._connections:
            self.ble.gatts_notify(conn_handle, self.handle_tx, data)

    def is_connected(self):
        return len(self._connections) > 0

    def _advertise(self, interval_us=500000):
        print("Starting advertising")
        self.ble.gap_advertise(interval_us, adv_data=self._payload)

    def on_write(self, callback):
        self._write_callback = callback


advertisement = AdvertisementHandler.load()
# characteristic = CharacteristicHandler(ble)

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3


# Register the service


def bt_irq(event: int, data: tuple):
    if event == 5:
        advertisement.handle_event(data)
        # print("adv", advertisement.setting_index)
        pass
    else:
        print("here")
        # characteristic.handle_event(event, data)
        pass


ble.irq(bt_irq)
ble.active(True)
ble.gap_scan(0)
