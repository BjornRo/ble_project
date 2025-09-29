# import micropython
# micropython.opt_level(3)

import aioble
import bluetooth
import uasyncio
import ujson
import utils
from aioble.client import ClientCharacteristic, ClientService
from machine import PWM, Pin

REMOTE_FILE = "remote"
SETTINGS_FILE = "settings"
SELECTED_SETTINGS_FILE = "selected_setting"


try:
    current_setting: str = utils.load_file(SELECTED_SETTINGS_FILE)
    if not current_setting.strip():
        raise Exception
    settings_cfg: dict[str, list[float]] = ujson.loads(utils.load_file(SETTINGS_FILE))
except:
    current_setting = "default"
    settings_cfg = dict(default=[0.0, 0.25, 0.5, 0.75, 1.0])
    utils.write_to_file(SELECTED_SETTINGS_FILE, current_setting)
    utils.write_to_file(SETTINGS_FILE, ujson.dumps(settings_cfg))
setting_index = 1  # Start from lowest


ConnHandle = int
ValueHandle = int
StartHandle = int
EndHandle = int
AddrType = int  # Mac: 0 = Public, 1 = Random
AdvertiseType = int  # advertisement event type
DefHandle = int  # handle of the characteristic declaration


def r(delete=False):
    import uos

    try:
        if delete:
            uos.remove(REMOTE_FILE)
    except:
        pass
    uasyncio.run(main())


async def main():
    ble = bluetooth.BLE()
    ble.active(True)

    try:
        await uasyncio.gather(
            RemoteHandler(ble, LED(26, settings_cfg["default"][setting_index])).serve(),
            # PhoneHandler(ble).serve(),
        )
    except BaseException as e:
        print(e)

    ble.active(False)


class LED:
    def __init__(self, pin: int, init_percentage=0.0, freq=1000) -> None:
        self.led = PWM(Pin(pin), freq=freq)
        self.control(init_percentage)

    def control(self, percentage: float):
        self.led.duty(round(1023 * percentage))


class RemoteHandler:
    REMOTE_SERVICE_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-000000000000")
    REMOTE_PAIRING_CHAR_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-000000000001")
    REMOTE_NOTIFY_CHAR_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-000000000002")
    DEFAULT_KEY = "rl-default"

    def __init__(self, ble: bluetooth.BLE, led: LED):
        self.ble = ble
        self.led = led
        try:
            with open(REMOTE_FILE, "rt") as f:
                self.remote_key = f.read()
        except:
            self.remote_key = self.DEFAULT_KEY

    async def serve(self, timeout=5000):
        while True:
            async with aioble.scan(0, 100_000, 100_000, True) as scanner:
                async for result in scanner:
                    name = result.name()
                    if name == self.remote_key and self.REMOTE_SERVICE_UUID in result.services():
                        assert name is not None
                        try:
                            await self.handle_conn(result.device, name)
                            # await uasyncio.wait_for_ms(self.handle_conn(result.device, name), timeout)
                        except BaseException as e:
                            print("waited for", e)
                        break

    async def handle_conn(self, device: aioble.Device, name: str):
        result: int = 2  # 0: Success, 1: Generate new keys, 2: Fail
        if len(name) == len(self.DEFAULT_KEY):
            if name == self.DEFAULT_KEY:
                result = 1
        else:
            result = 0
        if result != 2:
            try:
                print("connecting")
                async with await device.connect() as conn:
                    print("connected")
                    service = await conn.service(self.REMOTE_SERVICE_UUID)
                    assert service is not None

                    pairingchar: ClientCharacteristic
                    notifychar: ClientCharacteristic
                    pairingchar, notifychar = await uasyncio.gather(
                        service.characteristic(self.REMOTE_PAIRING_CHAR_UUID),
                        service.characteristic(self.REMOTE_NOTIFY_CHAR_UUID),
                    )
                    assert pairingchar is not None and notifychar is not None

                    if result == 1 and not await self.sync_keys(pairingchar):
                        return
                    print("notifydata receving")
                    data = await notifychar.notified()
                    print("notifydata", data)
                    if len(data) == 1:
                        await self.handle_notify(bool(int(data[0])))
                    print("end service", service)
            except uasyncio.TimeoutError as e:
                print("te", e)
            except uasyncio.CancelledError as e:
                print("ce", e)
            except BaseException as e:
                print("be", dir(e), e, repr(e))

    async def sync_keys(self, pairingchar: ClientCharacteristic) -> bool:
        try:
            print("syncing keys")
            new_key = "rl-" + utils.gen_random_string()
            await pairingchar.write(new_key, True)
            f = open(REMOTE_FILE, "wt")
            f.write(new_key)
            f.flush()
            self.remote_key = new_key
            print("syncing keys end")
            return True
        except aioble.GattError:
            pass
        print("syncing keys failed")
        return False

    async def handle_notify(self, increase: bool):
        global setting_index
        if increase:
            setting_index = min(len(settings_cfg[current_setting]) - 1, setting_index + 1)
        else:
            setting_index = max(0, setting_index - 1)
        self.led.control(settings_cfg[current_setting][setting_index])


class PhoneHandler:
    SERVICE_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-100000000000")
    JSON_DATA_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-100000000001")
    SETTING_DATA_UUID = bluetooth.UUID("A9DCFE62-41AF-49E3-ADC0-100000000002")

    def __init__(self, ble: bluetooth.BLE):
        self.ble = ble
        service = aioble.Service(self.SERVICE_UUID)
        self.json_characteristic = aioble.Characteristic(
            service,
            self.JSON_DATA_UUID,
            write=True,
            read=True,
            capture=True,
            notify=True,
        )
        self.setting_characteristic = aioble.Characteristic(
            service,
            self.SETTING_DATA_UUID,
            write=True,
            read=True,
            capture=True,
            notify=True,
        )
        aioble.register_services(service)
        self.connections: dict[ConnHandle, aioble.device.DeviceConnection] = {}

    async def serve(self, interval_us: int | None = 250_000, name="MyProject"):
        self.setting_characteristic.write(current_setting)
        self.json_characteristic.write(ujson.dumps(settings_cfg))
        tasks = [uasyncio.create_task(t) for t in (self.handle_json_char(), self.handle_setting_char())]
        while True:
            connection = await aioble.advertise(interval_us, name=name, services=[self.SERVICE_UUID])
            assert connection is not None
            assert connection._conn_handle is not None
            self.connections[connection._conn_handle] = connection
            try:
                await connection.disconnected(None)
            except:
                pass
            await self.force_disconnect(connection._conn_handle)

    async def force_disconnect(self, conn_handler: ConnHandle):
        try:
            conn = self.connections.pop(conn_handler)
            if conn._task is not None:
                conn._task.cancel()
            await conn.disconnect()
        except:
            pass

    async def handle_setting_char(self):
        global current_setting
        conn_handler: ConnHandle
        data: bytes
        while True:
            conn_handler, data = await self.setting_characteristic.written()  # type: ignore
            try:
                data_str = data.decode()
                if data_str and data_str in settings_cfg:
                    current_setting = data_str
                    self.setting_characteristic.write(data, True)
                    utils.write_to_file(SELECTED_SETTINGS_FILE, current_setting)
                    continue
            except:
                pass
            await self.force_disconnect(conn_handler)

    async def handle_json_char(self):
        global settings_cfg
        conn_handler: ConnHandle
        data: bytes
        while True:
            conn_handler, data = await self.json_characteristic.written()  # type: ignore
            try:
                new_config: dict[str, list[float]] = ujson.loads(data)
                for key, value in new_config.items():
                    if not key or not all((isinstance(v, float) and 0 <= v <= 1.0 for v in value)):
                        break
                else:
                    settings_cfg = new_config
                    self.json_characteristic.write(data, True)
                    utils.write_to_file(SETTINGS_FILE, ujson.dumps(settings_cfg))
                    continue
            except:
                pass
            await self.force_disconnect(conn_handler)


if __name__ == "__main__":
    uasyncio.run(main())
