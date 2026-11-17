# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import unittest
from pathlib import Path

from gc_texture import dxt1_to_cmpr, cmpr_to_dxt1

REFERENCE = Path('C:/SC2/tools/guests/textures.py')

class TextureTests(unittest.TestCase):
    def test_independent_endpoint_indices_and_padding(self):
        # c0 < c1 selects DXT1 transparency; indices 0,1,2,3 reverse per row.
        dxt = bytes.fromhex('34127856 e41b00ff')
        cmpr = bytes.fromhex('12345678 1be400ff') + bytes(24)
        for dimensions in ((1, 1), (4, 4)):
            self.assertEqual(dxt1_to_cmpr(dxt, *dimensions), cmpr)
            self.assertEqual(cmpr_to_dxt1(cmpr, *dimensions), dxt)

    def test_tile_subblock_order(self):
        # Distinct zero-index blocks show tile order over a 3x2 block grid.
        blocks = [bytes((i, 0, 0, 0, 0, 0, 0, 0)) for i in range(1, 7)]
        expected = b''.join(bytes((0, i, 0, 0, 0, 0, 0, 0)) for i in (1, 2, 4, 5, 3, 0, 6, 0))
        self.assertEqual(dxt1_to_cmpr(b''.join(blocks), 9, 8), expected)
        self.assertEqual(cmpr_to_dxt1(expected, 9, 8), b''.join(blocks))
        self.assertEqual(len(dxt1_to_cmpr(b''.join(blocks[:4]), 8, 8)), 32)

    def test_reference_forward_conversion(self):
        spec = importlib.util.spec_from_file_location('reference_textures', REFERENCE)
        ref = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ref)
        for w, h in ((1, 1), (4, 4), (8, 8), (9, 13), (16, 7)):
            size = ((w + 7) // 8) * ((h + 7) // 8) * 32
            original = bytes((i * 73 + 19) & 255 for i in range(size))
            dxt = ref.cmpr_blocks(original, w, h)
            self.assertEqual(cmpr_to_dxt1(original, w, h), dxt)
            self.assertEqual(ref.cmpr_blocks(dxt1_to_cmpr(dxt, w, h), w, h), dxt)

    def test_invalid(self):
        for dim in (0, -1, 1025, True, 1.0, '1'):
            for fn in (dxt1_to_cmpr, cmpr_to_dxt1):
                with self.assertRaises(ValueError): fn(b'', dim, 1)
                with self.assertRaises(ValueError): fn(b'', 1, dim)
        for fn, size in ((dxt1_to_cmpr, 8), (cmpr_to_dxt1, 32)):
            for n in (0, size - 1, size + 1):
                with self.assertRaises(ValueError): fn(bytes(n), 1, 1)
            with self.assertRaises(TypeError): fn('x', 1, 1)

    def test_typed_memoryview(self):
        block = bytes.fromhex('34127856 e41b00ff')
        expected = bytes.fromhex('12345678 1be400ff') + bytes(24)
        self.assertEqual(dxt1_to_cmpr(memoryview(block).cast('H'), 4, 4), expected)
        with self.assertRaises(ValueError):
            dxt1_to_cmpr(memoryview(block * 2).cast('H'), 4, 4)

if __name__ == '__main__': unittest.main()
