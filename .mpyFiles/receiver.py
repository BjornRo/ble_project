import _thread
import time

import bluetooth
import ujson
import uos
import utils


class RemoteHandler:
    def __init__(self, ble: bluetooth.BLE, remote_file="remote"):
        self.ble = ble
        try:
            with open(remote_file, "rb") as f:
                self.remote_key = f.read()
                self.paired = True
        except:
            self.remote_key = b"\xca\xfe\x13\x37"
            self.paired = False

    def run(self):
        self.ble.gap_scan(0, 100_000, 90_000)

    def handle_request(self, data: tuple[int, memoryview, int, int, memoryview]):
        addr_type, mac_addr, adv_type, rssi, adv_data = data
        if self.paired:
            pass
        elif adv_data[2:6] == self.remote_key:
            pass


class PhoneHandler:
    def __init__(self, ble: bluetooth.BLE, callback_func, name=b"mpy-uart"):
        self.ble = ble
        ((self.handle_tx, self.handle_rx),) = self.ble.gatts_register_services((utils.UART_SERVICE,))
        self.connections = set()
        self.write_callback = callback_func
        self.payload = utils.advertising_payload(name=name, services=[utils.UART_UUID])

    def handle_request(self, event: int, data: tuple):
        if event == utils.IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self.connections.add(conn_handle)
        elif event == utils.IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self.connections.remove(conn_handle)
            self.advertise()
        elif event == utils.IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self.ble.gatts_read(value_handle)
            if value_handle == self.handle_rx and self.write_callback:
                self.write_callback(value)

    def send(self, data: bytes):
        for conn_handle in self.connections:
            self.ble.gatts_notify(conn_handle, self.handle_tx, data)

    def is_connected(self):
        return len(self.connections) > 0

    def advertise(self, interval_us=500000):
        print("Starting advertising")
        self.ble.gap_advertise(interval_us, adv_data=self.payload)

    def on_write(self, callback):
        self.write_callback = callback


class BLEHandler:
    def __init__(self, ble: bluetooth.BLE, remote: RemoteHandler, phone: PhoneHandler):
        self.ble = ble
        self.remote = remote
        self.phone = phone

    def run(self):
        self.ble.irq(self.event_handler)
        self.ble.active(True)
        self.remote.run()

    def event_handler(self, event: int, data: tuple):
        if event == utils.IRQ_SCAN_RESULT:
            self.remote.handle_request(data)
        else:
            self.phone.handle_request(event, data)


ble = bluetooth.BLE()


def on_rx(value):
    print("RX:", value)


handler = BLEHandler(ble, on_rx)
