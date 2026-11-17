# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import unittest
from unittest.mock import patch
import gc_motion as m


def motion(frames=9, flags=0, channels=4, pose_value=2):
    blocks=m.motion_blocks(frames,flags)
    header=bytearray(0x1c+2*blocks)
    struct.pack_into('>HHI',header,0,frames,channels,flags)
    struct.pack_into('>Q',header,8,0x0123456789abcdef)
    struct.pack_into('>H',header,0x10,0x1234)
    struct.pack_into('<H',header,0x18,pose_value)
    start=len(header)+3
    previous=0x1c
    for i in range(blocks):
        p=start+i*(channels+3)
        struct.pack_into('>h',header,0x1c+2*i,p-previous)
        previous=p
    data=header+bytearray(b'P'*3)
    for i in range(blocks):
        data.extend(bytes(range(1,channels+1)));data.extend(b'XYZ')
    return bytes(data)


def bank(*motions):
    header=bytearray(8+4*len(motions));struct.pack_into('>II',header,0,len(motions),0x01234567)
    pos=len(header)
    for i,item in enumerate(motions):
        struct.pack_into('>I',header,8+4*i,pos);pos+=len(item)
    return bytes(header)+b''.join(motions)


def table_pack(*parts):
    offset = 4 * (len(parts) + 2)
    offsets = [offset]
    for part in parts:
        offset += len(part)
        offsets.append(offset)
    return struct.pack('>' + str(len(offsets) + 1) + 'I', len(parts), *offsets) + b''.join(parts)


class MotionTests(unittest.TestCase):
    def test_roundtrip_flags_and_padding(self):
        for flag, frames in [(0,17),(4,17),(8,33),(12,33),(0,0)]:
            with self.subTest(flag=flag,frames=frames):
                x=motion(frames,flag); y=m.gamecube_to_xbox_motion(x)
                self.assertEqual(m.xbox_to_gamecube_motion(y),x)
                self.assertEqual(y[-3:],x[-3:])
    def test_bank_roundtrip_empty_and_padding(self):
        for x in [bank(),bank(motion(),b'',motion(3,4)),bank()+b'padding']:
            self.assertEqual(m.xbox_to_gamecube_bank(m.gamecube_to_xbox_bank(x)),x)
    def test_pose_roundtrip_and_adjustment(self):
        x=bank(motion(1,pose_value=0x1234));y=m.gamecube_to_xbox_pose_bank(x)
        self.assertEqual(struct.unpack_from('<H',y,12+0x18)[0],0x1254)
        self.assertEqual(m.xbox_to_gamecube_pose_bank(y),x)
        self.assertEqual(m.xbox_to_gamecube_pose_bank(m.gamecube_to_xbox_pose_bank(bank())),bank())
    def test_truncated_invalid_order_and_odd(self):
        for value in [b'',b'1234567']:
            with self.assertRaises(ValueError): m.convert_bank(value,'big')
        with self.assertRaises(ValueError): m.convert_motion(b'\0'*27,'big')
        with self.assertRaises(ValueError): m.convert_motion(motion(channels=3),'big')
        with self.assertRaises(ValueError): m.convert_bank(bank(),'unknown')
    def test_bad_count_offsets(self):
        with self.assertRaises(ValueError): m.convert_bank(struct.pack('>II',0xffffffff,0),'big')
        for offsets in [(8,12),(20,19),(20,9999)]:
            raw=struct.pack('>IIII',2,0,*offsets)+b'\0'*24
            with self.subTest(offsets=offsets),self.assertRaises(ValueError): m.convert_bank(raw,'big')
    def test_bad_blocks(self):
        x=bytearray(motion())
        for step in [-1,0,1,32767]:
            y=x.copy();struct.pack_into('>h',y,0x1c,step)
            with self.subTest(step=step),self.assertRaises(ValueError): m.convert_motion(y,'big')
        y=x.copy();struct.pack_into('>h',y,0x1e,1)
        with self.assertRaises(ValueError): m.convert_motion(y,'big')
        with self.assertRaises(ValueError): m.convert_motion(x[:0x1d],'big')
    def test_reject_unrecognized_pose(self):
        with self.assertRaises(ValueError): m.convert_pose_bank(bank(motion(2)),'big')
        with self.assertRaises(ValueError): m.convert_pose_bank(bank(motion(1,pose_value=0xffff)),'big')
        x=bytearray(m.gamecube_to_xbox_pose_bank(bank(motion(1))))
        struct.pack_into('<H',x,12+0x18,0x1f)
        with self.assertRaises(ValueError): m.convert_pose_bank(x,'little')

    def test_moveset_tables_roundtrip_and_padding(self):
        part0 = bytes(range(60)) + b'padding'
        part1 = bytes(range(48)) + b'pad'
        camera = bytes(range(17))
        x = table_pack(part0, part1, camera, bytes(range(11))) + b'tail'
        y = m.gamecube_to_xbox_moveset_tables(x)
        self.assertEqual(m.xbox_to_gamecube_moveset_tables(y), x)
        start = 4 * (4 + 2)
        self.assertEqual(y[start:start + 48], part0[:48])
        self.assertEqual(y[start + 60:start + 67], b'padding')
        self.assertEqual(y[-4:], b'tail')
        self.assertEqual(m.xbox_to_gamecube_moveset_tables(m.gamecube_to_xbox_moveset_tables(table_pack())), table_pack())

    def test_moveset_parts_preserved(self):
        p = [b'bytecode', bank(motion()), table_pack(bytes(range(60))), b'unknown']
        q = m.gamecube_to_xbox_moveset(p)
        self.assertEqual(q[0], p[0]); self.assertEqual(q[3], p[3])
        self.assertEqual(m.xbox_to_gamecube_moveset(q), p)
        self.assertEqual(m.convert_moveset([b'x', b'', b'', b'other'], 'big'), [b'x', b'', b'', b'other'])

    def test_moveset_table_rejects_bad_structure(self):
        with self.assertRaises(ValueError): m.convert_moveset_tables(b'1234567','big')
        with self.assertRaises(ValueError): m.convert_moveset_tables(struct.pack('>II', 0xffffffff, 0),'big')
        for offsets in [(8, 16), (20, 19), (20, 9999)]:
            raw = struct.pack('>IIII', 2, *offsets, 20) + bytes(40)
            with self.subTest(offsets=offsets), self.assertRaises(ValueError): m.convert_moveset_tables(raw, 'big')
        with self.assertRaises(ValueError): m.convert_moveset_tables(table_pack(b'', b'1234567'),'big')
        with self.assertRaises(ValueError): m.convert_moveset_tables(table_pack(b'', bytes(8), b'1234567'),'big')
        with self.assertRaises(ValueError): m.convert_moveset([], 'unknown')

    def test_moveset_pack_roundtrip_and_preservation(self):
        parts = [b'code\x00\xff', bank(motion()), table_pack(bytes(range(60))), b'other']
        header_end = 4 * (len(parts) + 2)
        offsets = [header_end + 3]
        for part in parts: offsets.append(offsets[-1] + len(part))
        original = struct.pack('>6I', len(parts), *offsets) + b'PAD' + b''.join(parts) + b'TRAILING'
        converted = m.gamecube_to_xbox_moveset_pack(original)
        self.assertEqual(len(converted), len(original))
        self.assertEqual(converted[header_end:offsets[0]], b'PAD')
        self.assertEqual(converted[offsets[0]:offsets[1]], parts[0])
        self.assertEqual(converted[offsets[3]:offsets[4]], parts[3])
        self.assertEqual(converted[offsets[-1]:], b'TRAILING')
        self.assertEqual(m.xbox_to_gamecube_moveset_pack(converted), original)
        self.assertEqual(m.gamecube_to_xbox_moveset_pack(m.xbox_to_gamecube_moveset_pack(converted)), converted)
        empty = table_pack(b'code', b'', b'', b'extra')
        self.assertEqual(m.xbox_to_gamecube_moveset_pack(m.gamecube_to_xbox_moveset_pack(empty)), empty)

    def test_moveset_pack_rejects_invalid_and_changed_size(self):
        for data in (b'', bytes(7), struct.pack('>II', 0, 8),
                     struct.pack('>II', 4097, 8), struct.pack('>II', 2, 8),
                     struct.pack('>III', 1, 8, 12),
                     struct.pack('>III', 1, 12, 11),
                     struct.pack('>III', 1, 12, 99)):
            with self.subTest(data=data), self.assertRaises(ValueError): m.convert_moveset_pack(data, 'big')
        with patch.object(m, 'convert_moveset', return_value=[b'changed size']):
            with self.assertRaises(ValueError): m.convert_moveset_pack(table_pack(b'x'), 'big')

if __name__ == '__main__': unittest.main()
