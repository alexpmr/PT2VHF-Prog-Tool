import os
import tempfile
import threading
import unittest

from ts2000prog import protocol as P
from ts2000prog.fileio import (Codeplug, export_csv, import_csv, load_project,
                               save_project)
from ts2000prog.menus import load_menu_defs
from ts2000prog.radio import SIMULATOR_PORT, TS2000, Cancelled, RadioError


def noprog(*a):
    pass


class ProtocolTests(unittest.TestCase):
    def test_write_matches_hamlib_layout(self):
        m = P.Memory(1, False, 146_940_000, 4, tone_mode=1, tone=12, shift=2,
                     offset=600_000, step=6, name="RPT")
        self.assertEqual(P.cmds_write_memory(m), [
            "MW0001" "00146940000" "4" "0" "1" "12" "08" "000" "0" "2"
            "000600000" "06" "0" "RPT;"])

    def test_tone_off_zeroes_tone_fields(self):
        m = P.Memory(5, False, 7_000_000, 3, tone=20, ctcss=20, dcs=50)
        body = P.cmds_write_memory(m)[0]
        self.assertEqual(body[6 + 13:6 + 20], "0000000")

    def test_parse_round_trip(self):
        m = P.Memory(42, False, 439_975_000, 4, lockout=True, tone_mode=3,
                     dcs=103, reverse=True, shift=2, offset=5_000_000,
                     step=9, group=7, name="ABCDEFGH")
        reply = "MR" + P.cmds_write_memory(m)[0][2:]
        back = P.memory_from_replies(42, reply, None)
        self.assertEqual(back.to_dict(), m.to_dict())

    def test_empty_reply(self):
        m = P.memory_from_replies(7, "MR0007" + "0" * 35 + ";", None)
        self.assertTrue(m.empty)

    def test_split_and_erase(self):
        m = P.Memory(4, False, 14_195_000, 2, tx_freq=14_225_000, tx_mode=3)
        cmds = P.cmds_write_memory(m)
        self.assertEqual(len(cmds), 2)
        self.assertTrue(cmds[1].startswith("MW100400014225000" "3"))
        self.assertEqual(P.cmds_write_memory(P.Memory(4)),
                         ["MW0004" + "0" * 35 + ";"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            P.Memory(1, False, 145_000_000, 4, name="NOVE CHAR").validate()
        with self.assertRaises(ValueError):
            P.Memory(1, False, 145_000_000, 2, step=5).validate()
        with self.assertRaises(ValueError):
            P.Memory(300).validate()

    def test_menu_commands(self):
        self.assertEqual(P.cmd_read_menu(12), "EX0120000;")
        self.assertEqual(P.cmd_write_menu(31, 0, "06"), "EX0310000" "06;")
        self.assertEqual(P.parse_menu_reply("EX01200004;"), (12, 0, "4"))


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.r = TS2000()
        self.assertEqual(self.r.connect(SIMULATOR_PORT), "ID019")

    def tearDown(self):
        self.r.disconnect()

    def test_download_upload_cycle(self):
        mems = self.r.download_memories(range(0, 10), noprog)
        self.assertEqual(mems[1].name, "RPT 2M")
        self.assertEqual(P.TONES[mems[1].tone - 1], 100.0)
        self.assertTrue(mems[4].split)
        self.assertTrue(mems[9].empty)

        new = P.Memory(9, False, 50_125_000, 2, step=1, group=3, name="6M")
        errs = self.r.upload_memories([new, P.Memory(0)], noprog, verify=True)
        self.assertEqual(errs, [])
        self.assertEqual(self.r.read_memory(9).to_dict(), new.to_dict())
        self.assertTrue(self.r.read_memory(0).empty)

    def test_program_scan_channel(self):
        m = self.r.read_memory(290)
        self.assertEqual((m.freq, m.tx_freq), (144_000_000, 148_000_000))

    def test_menus(self):
        defs, _ = load_menu_defs()
        vals, errs = self.r.download_menus(defs, noprog)
        self.assertEqual(errs, [])
        beep = next(d for d in defs if d.label == "12")
        self.assertEqual(self.r.upload_menus([(beep, "7")], noprog), [])
        self.assertEqual(self.r.read_menu(12), "7")
        with self.assertRaises(RadioError):
            self.r.write_menu(99, 0, "1")

    def test_scan(self):
        found = self.r.scan_menus(range(0, 15), range(2), noprog)
        self.assertIn("00601", found)
        self.assertIn("01200", found)
        self.assertNotIn("01201", found)

    def test_cancel(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(Cancelled):
            self.r.download_memories(range(10), noprog, ev)


class FileTests(unittest.TestCase):
    def test_project_and_csv(self):
        cp = Codeplug()
        cp.memories[3] = P.Memory(3, False, 439_975_000, 4, tone_mode=2,
                                  ctcss=39, shift=2, offset=5_000_000, step=6,
                                  name="UHF")
        cp.memories[4] = P.Memory(4, False, 14_195_000, 2,
                                  tx_freq=14_225_000)
        cp.menus["01200"] = "5"
        with tempfile.TemporaryDirectory() as d:
            pj = os.path.join(d, "x.ts2k")
            save_project(cp, pj)
            back = load_project(pj)
            self.assertEqual(back.memories[3].to_dict(),
                             cp.memories[3].to_dict())
            self.assertEqual(back.menus, {"01200": "5"})

            csvp = os.path.join(d, "x.csv")
            self.assertEqual(export_csv(cp, csvp), 2)
            mems, errs = import_csv(csvp)
            self.assertEqual(errs, [])
            self.assertEqual([m.to_dict() for m in mems],
                             [cp.memories[3].to_dict(),
                              cp.memories[4].to_dict()])


if __name__ == "__main__":
    unittest.main()
