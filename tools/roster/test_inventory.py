# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import unittest

from inventory import FormatError, Olnk, pack_parts


def olnk(entries):
    header = 32 + 16 * len(entries)
    out = bytearray(header)
    struct.pack_into('<I4sII', out, 0, len(entries), b'olnk', 16, 0)
    struct.pack_into('<I', out, 16, header)
    for i, value in enumerate(entries):
        if value is not None:
            struct.pack_into('<II', out, 32 + 16 * i, len(out) - header, len(value))
            out.extend(value)
    struct.pack_into('<I', out, 20, len(out) - header)
    return out


def pack(order):
    return struct.pack(order + '4I', 2, 16, 19, 19) + b'abc'


class Tests(unittest.TestCase):
    def test_nested_and_hole(self):
        data = olnk([None, olnk([b'abc'])])
        root = Olnk(data)
        self.assertEqual(root.entry(0)[1], 0)
        with self.assertRaises(FormatError): root.child(0)
        node = root.child(1)
        at, size, _ = node.entry(0)
        self.assertEqual(data[at:at + size], b'abc')

    def test_truncation_and_count(self):
        for data in (b'olnk', olnk([b'x'])[:35]):
            with self.assertRaises(FormatError): Olnk(data)
        data = olnk([])
        struct.pack_into('<I', data, 0, 0xffffffff)
        with self.assertRaises(FormatError): Olnk(data)

    def test_header_and_offsets(self):
        data = olnk([b'x'])
        struct.pack_into('<I', data, 16, 33)
        with self.assertRaises(FormatError): Olnk(data)
        data = olnk([b'x'])
        struct.pack_into('<I', data, 32, 0xffffffff)
        with self.assertRaises(FormatError): Olnk(data)

    def test_child_cannot_escape_parent_even_if_backing_has_bytes(self):
        child = olnk([b'abc'])
        parent = olnk([child])
        at, size, _ = Olnk(parent).entry(0)
        struct.pack_into('<I', parent, at + 36, size)
        parent.extend(b'X' * size)
        with self.assertRaises(FormatError): Olnk(parent).child(0)

    def test_pack_endian_and_empty_part(self):
        for byte_order, prefix, wrong in [('big', '>', 'little'), ('little', '<', 'big')]:
            data = pack(prefix)
            self.assertEqual(pack_parts(data, 0, len(data), byte_order), [(16, 3), (19, 0)])
            self.assertIsNone(pack_parts(data, 0, len(data), wrong))

    def test_pack_bad_count_offsets_and_truncation(self):
        for data in (struct.pack('>I', 0xffffffff) + b'\0' * 12,
                     struct.pack('>4I', 2, 16, 15, 19) + b'abc',
                     struct.pack('>4I', 2, 12, 16, 19) + b'abc',
                     pack('>')[:-1]):
            self.assertIsNone(pack_parts(data, 0, len(data), 'big'))
        with self.assertRaises(FormatError): pack_parts(b'1234', 2, 3, 'big')


if __name__ == '__main__':
    unittest.main()
