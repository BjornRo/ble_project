import time

import bluetooth
import ujson

ble = bluetooth.BLE()


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
        if adv_data[2:6] == b"\xca\xfe\x12\x34" and len(adv_data) == 7:
            if self.remote_mac_addr is None:
                remote_mac_addr = bytes(mac_addr)
                f = open(self.remote_file, "wb")
                f.write(remote_mac_addr)
                f.flush()
                del f
            elif self.remote_mac_addr == mac_addr:
                now = time.ticks_ms()
                if time.ticks_diff(now, self.last_message) >= self.cooldown_ms:
                    self.last_message = now  # update last_message
                    self.increase_setting() if adv_data[6] == 2 else self.decrease_setting()

    @staticmethod
    def load(settings_file="settings"):
        try:
            with open(settings_file, "rt") as f:
                __curr_setting = f.readline()
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
        SERVICE_UUID = bluetooth.UUID(0x180F)
        CHAR_UUID = bluetooth.UUID(0x2A19)
        self._handle = None
        # ble.gap_advertise(None)

        ((self._handle,),) = ble.gatts_register_services(
            ((SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE),)),)
        )

    def handle_event(self, data):
        conn_handle, value_handle = data
        if value_handle == self._handle:
            value = ble.gatts_read(self._handle)
            print("Characteristic written:", value)


advertisement = AdvertisementHandler.load()
characteristic = CharacteristicHandler(ble)


def bt_irq(event, data):
    if event == 3:
        characteristic.handle_event(data)
    elif event == 5:
        advertisement.handle_event(data)


ble.irq(bt_irq)
ble.active(True)
ble.gap_scan(0)
