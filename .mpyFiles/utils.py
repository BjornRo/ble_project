import binascii
import hashlib
import time


def gen_random_string(chars=16) -> str:
    # return ((urandom.getrandbits(32) << 32) | urandom.getrandbits(32)).to_bytes(8)
    return binascii.hexlify(hashlib.sha1(time.ticks_us().to_bytes(chars // 2)).digest()[: chars // 2]).decode()


def write_to_file(file: str, value: str):
    with open(file, "wt") as f:
        return f.write(value)


def load_file(file: str):
    with open(file, "rt") as f:
        return f.read()
