"""Aviso do site oficial: sempre na abertura e, depois dele, o aviso de versão nova."""

import gc
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    from common import update_ui
except ImportError:          # Python sem Tkinter
    tk = update_ui = None


def _display() -> bool:
    if tk is None:
        return False
    try:
        root = tk.Tk()
        root.destroy()
        del root
        gc.collect()      # coleta o Tcl aqui, não numa thread de outro teste
        return True
    except tk.TclError:
        return False


@unittest.skipIf(tk is None, "sem Tkinter")
class SiteNoticeText(unittest.TestCase):
    def test_text_points_to_official_site(self):
        self.assertIn("somente pelo site oficial", update_ui.SITE_NOTICE_TEXT)
        self.assertEqual(update_ui.SITE_URL, "https://www.pt2vhf.com/prog")

    def test_no_opt_out(self):
        src = open(update_ui.__file__, encoding="utf-8").read()
        notice = src[src.index("class SiteNoticeDialog"):
                     src.index("class UpdateDialog")]
        self.assertNotIn("Checkbutton", notice)
        self.assertNotIn("config", notice)


@unittest.skipUnless(_display(), "sem display")
class SiteNoticeSequence(unittest.TestCase):
    def test_notice_first_then_update_check(self):
        from launcher.app import Launcher
        with mock.patch.object(Launcher, "_auto_check") as auto:
            app = Launcher()
            try:
                app.update()
                app.after(400, lambda: None)
                for _ in range(10):
                    app.update()
                    app.after(60)
                notices = [w for w in app.winfo_children()
                           if isinstance(w, update_ui.SiteNoticeDialog)]
                self.assertEqual(len(notices), 1)
                auto.assert_not_called()          # ainda não verificou
                notices[0].close()
                auto.assert_called_once_with()    # em sequência
            finally:
                app.destroy()
                del app
                gc.collect()

    def test_shown_again_on_next_start(self):
        from launcher.app import Launcher
        for _ in range(2):
            with mock.patch.object(Launcher, "_auto_check"):
                app = Launcher()
                try:
                    app.show_site_notice()
                    self.assertTrue(any(
                        isinstance(w, update_ui.SiteNoticeDialog)
                        for w in app.winfo_children()))
                finally:
                    app.destroy()
                    del app
                    gc.collect()


if __name__ == "__main__":
    unittest.main()
