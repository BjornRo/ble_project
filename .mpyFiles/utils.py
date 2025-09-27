import struct

import bluetooth
import uhashlib
import utime


def gen_key() -> bytes:
    # return ((urandom.getrandbits(32) << 32) | urandom.getrandbits(32)).to_bytes(8)
    return uhashlib.sha1(utime.ticks_us().to_bytes(8)).digest()[:8]


IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3
IRQ_GATTS_READ_REQUEST = 4
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6
IRQ_PERIPHERAL_CONNECT = 7
IRQ_PERIPHERAL_DISCONNECT = 8
IRQ_GATTC_SERVICE_RESULT = 9
IRQ_GATTC_SERVICE_DONE = 10
IRQ_GATTC_CHARACTERISTIC_RESULT = 11
IRQ_GATTC_CHARACTERISTIC_DONE = 12
IRQ_GATTC_DESCRIPTOR_RESULT = 13
IRQ_GATTC_DESCRIPTOR_DONE = 14
IRQ_GATTC_READ_RESULT = 15
IRQ_GATTC_READ_DONE = 16
IRQ_GATTC_WRITE_DONE = 17
IRQ_GATTC_NOTIFY = 18
IRQ_GATTC_INDICATE = 19

FLAG_READ = 0x0002
FLAG_WRITE_NO_RESPONSE = 0x0004
FLAG_WRITE = 0x0008
FLAG_NOTIFY = 0x0010


ADV_TYPE_FLAGS = 0x01
ADV_TYPE_NAME = 0x09
ADV_TYPE_UUID16_COMPLETE = 0x3
ADV_TYPE_UUID32_COMPLETE = 0x5
ADV_TYPE_UUID128_COMPLETE = 0x7
ADV_TYPE_UUID16_MORE = 0x2
ADV_TYPE_UUID32_MORE = 0x4
ADV_TYPE_UUID128_MORE = 0x6
ADV_TYPE_APPEARANCE = 0x19

ADV_MAX_PAYLOAD = 31


UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
    FLAG_READ | FLAG_NOTIFY,
)
UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
    FLAG_WRITE | FLAG_WRITE_NO_RESPONSE,
)
UART_SERVICE = (UART_UUID, (UART_TX, UART_RX))


def advertising_payload(
    limited_disc=False,
    br_edr=False,
    name: bytes | None = None,
    services: list[bluetooth.UUID] | None = None,
    appearance=0,
):
    payload = bytearray()

    def _append(adv_type: int, value: bytes):
        nonlocal payload
        payload += struct.pack("BB", len(value) + 1, adv_type) + value

    _append(
        ADV_TYPE_FLAGS,
        struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
    )

    if name:
        _append(ADV_TYPE_NAME, name)

    if services:
        for uuid in services:
            b = bytes(uuid)  # type: ignore
            if len(b) == 2:
                _append(ADV_TYPE_UUID16_COMPLETE, b)
            elif len(b) == 4:
                _append(ADV_TYPE_UUID32_COMPLETE, b)
            elif len(b) == 16:
                _append(ADV_TYPE_UUID128_COMPLETE, b)

    if appearance:
        _append(ADV_TYPE_APPEARANCE, struct.pack("<h", appearance))

    if len(payload) > ADV_MAX_PAYLOAD:
        raise ValueError("advertising payload too large")

    return payload
