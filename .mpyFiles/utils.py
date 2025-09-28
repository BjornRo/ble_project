import uhashlib
import utime


def gen_64bits() -> bytes:
    # return ((urandom.getrandbits(32) << 32) | urandom.getrandbits(32)).to_bytes(8)
    return uhashlib.sha1(utime.ticks_us().to_bytes(8)).digest()[:8]


def write_to_file(file: str, value: str):
    with open(file, "wt") as f:
        return f.write(value)


def load_file(file: str):
    with open(file, "rt") as f:
        return f.read()
