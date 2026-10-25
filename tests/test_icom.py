import os
import tempfile
import unittest

from icomprog import clone as C
from icomprog.icf import read_icf, write_icf
from icomprog.models import MODELS, IcomMemory
from icomprog.simulator import SimulatedIcom


def noprog(*a):
    pass


class CodecTests(unittest.TestCase):
    def test_round_trip_all_fields(self):
        for model in MODELS.values():
            img = model.blank_image()
            m = IcomMemory(7, False, 439_412_500, 5_000_000, duplex=1,
                           mode=5, name="TESTE", tmode=model.default_dtcs,
                           rtone=12, ctone=20, dtcs=50, dtcs_pol=2, step=5,
                           skip="P", bank=3, bank_index=12, urcall="CQCQCQ",
                           rpt1="PY2ABC B", rpt2="PY2ABC G", dv_code=9)
            model.encode(img, m)
            self.assertEqual(model.decode(img, 7).to_dict(), m.to_dict(),
                             model.name)
            model.encode(img, IcomMemory(7))
            self.assertTrue(model.decode(img, 7).empty)

    def test_unknown_bits_preserved(self):
        model = MODELS["id51plus2"]
        img = model.blank_image()
        model.encode(img, IcomMemory(1, False, 145_000_000))
        img[1 * 49 + 9] = 0xA5          # byte desconhecido
        m = model.decode(img, 1)
        m.name = "NOVO"
        model.encode(img, m)
        self.assertEqual(img[1 * 49 + 9], 0xA5)

    def test_validation(self):
        model = MODELS["id880h"]
        with self.assertRaises(ValueError):
            model.validate(IcomMemory(0, False, 50_000_000))   # fora da faixa
        with self.assertRaises(ValueError):
            model.validate(IcomMemory(0, False, 145_000_000,
                                      name="NOME LONGO"))
        with self.assertRaises(ValueError):
            MODELS["id51plus2"].validate(IcomMemory(0, False, 145_000_000,
                                                    step=2))

    def test_raw_escape(self):
        data = bytes(range(0xF0, 0x100))
        self.assertEqual(C.unescape_raw(C.escape_raw(data)), data)
        self.assertNotIn(0xFD, C.escape_raw(data))


class CloneTests(unittest.TestCase):
    def test_clone_both_directions(self):
        for model in MODELS.values():
            for echo in (False, True):
                sim = SimulatedIcom(model, echo=echo)
                img = C.clone_from_radio(sim, model, noprog)
                self.assertEqual(model.decode(img, 0).name, "CHAMADA")
                model.encode(img, IcomMemory(9, False, 145_250_000,
                                             name="NOVO"))
                C.clone_to_radio(sim, model, img, noprog)
                again = C.clone_from_radio(sim, model, noprog)
                self.assertEqual(again, img)

    def test_wrong_model_rejected(self):
        sim = SimulatedIcom(MODELS["id880h"])
        with self.assertRaises(C.CloneError):
            C.clone_from_radio(sim, MODELS["id51plus2"], noprog)


class IcfTests(unittest.TestCase):
    def test_write_read(self):
        for model in MODELS.values():
            img = model.blank_image()
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "x.icf")
                write_icf(p, model.model_id, model.icf_meta, img,
                          model.icf_recordsize)
                mid, meta, back = read_icf(p)
            self.assertEqual((mid, back), (model.model_id, img))
            self.assertEqual(meta["MapRev"], 1)


if __name__ == "__main__":
    unittest.main()
