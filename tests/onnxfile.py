'''Make a tiny ONNX file without the ``onnx`` package.

The tests of the DNN code need a network that OpenCV can read.  An ONNX
file is a protocol buffer, and one node of one operator takes a few lines to
write by hand, so the tests need neither ``onnx`` nor a model of anyone's.
'''
from pathlib import Path


__all__ = ['writeIdentity']


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field(number: int, wire: int, payload: bytes) -> bytes:
    return _varint(number << 3 | wire) + payload


def _bytes(number: int, data: bytes) -> bytes:
    return _field(number, 2, _varint(len(data)) + data)


def _int(number: int, value: int) -> bytes:
    return _field(number, 0, _varint(value))


def _valueInfo(name: str, shape: tuple[int, ...]) -> bytes:
    dims = b''.join(_bytes(1, _int(1, n)) for n in shape)  # Dimension
    tensor = _int(1, 1) + _bytes(2, dims)                  # float32, shape
    return _bytes(1, name.encode()) + _bytes(2, _bytes(1, tensor))


def writeIdentity(path: str | Path, shape: tuple[int, ...]) -> Path:
    '''Write a network whose output is its input, and return *path*.

    Parameters
    ----------
    path : str or Path
        The file to write.
    shape : tuple of int
        Shape of the input and the output, for example ``(1, 3, 32, 32)``.
    '''
    node = (_bytes(1, b'input') + _bytes(2, b'output')
            + _bytes(3, b'identity') + _bytes(4, b'Identity'))
    graph = (_bytes(1, node) + _bytes(2, b'identity')
             + _bytes(11, _valueInfo('input', shape))
             + _bytes(12, _valueInfo('output', shape)))
    model = (_int(1, 8) + _bytes(7, graph)
             + _bytes(8, _int(2, 13)))                      # opset 13
    path = Path(path)
    path.write_bytes(model)
    return path
