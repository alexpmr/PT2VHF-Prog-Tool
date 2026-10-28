import base64
import functools
import hashlib
import http.server
import json
import os
import tempfile
import threading
import unittest

from common import ed25519
from common import updater as U

KEY = bytes(range(32))
PUB = ed25519.public_key(KEY)


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.payload = b"pacote de teste" * 1000
        with open(os.path.join(self.dir, "p.tar.gz"), "wb") as fh:
            fh.write(self.payload)
        h = functools.partial(http.server.SimpleHTTPRequestHandler,
                              directory=self.dir)
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}/"
        os.environ["PT2VHF_UPDATE_URL"] = self.base + "update.php?product=prog"
        self.orig_key = U.PUBLIC_KEY
        U.PUBLIC_KEY = PUB

    def tearDown(self):
        self.srv.shutdown()
        U.PUBLIC_KEY = self.orig_key
        os.environ.pop("PT2VHF_UPDATE_URL", None)

    def publish(self, sha=None, key=KEY, sign=True, url=None,
                version="9.9.9"):
        digest = sha or hashlib.sha256(self.payload).hexdigest()
        entry = {"category": "linux-targz", "label": "Linux — .tar.gz",
                 "name": "p.tar.gz", "url": url or self.base + "p.tar.gz",
                 "size": len(self.payload), "sha256": digest}
        if sign:
            entry["sig"] = base64.b64encode(ed25519.sign(
                key, U.signed_text(version, "p.tar.gz", digest))).decode()
        # mesmo formato devolvido pelo update.php do site
        cat = {"schema": 1, "source": "https://www.pt2vhf.com",
               "product": "prog",
               "status": "available" if version else "unpublished",
               "version": version or None, "date": "2026-10-28",
               "notes": "a; b", "page": "https://www.pt2vhf.com/prog",
               "files": [dict(entry, kind="tar.gz", platform="")]
               if version else []}
        with open(os.path.join(self.dir, "update.php"), "w") as fh:
            json.dump(cat, fh)

    def test_check_and_download(self):
        self.publish()
        info = U.check()
        self.assertTrue(U.is_newer(info.version, "1.3.0"))
        self.assertEqual(info.notes, ["a", "b"])
        out = tempfile.mkdtemp()
        path = U.download(info.files["tgz"], out)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), self.payload)

    def test_bad_or_missing_signature_rejected(self):
        for kwargs in ({"key": bytes(32)}, {"sign": False}):
            self.publish(**kwargs)
            info = U.check()
            out = tempfile.mkdtemp()
            with self.assertRaises(U.UpdateError):
                U.download(info.files["tgz"], out)
            self.assertEqual(os.listdir(out), [])

    def test_signature_bound_to_version(self):
        self.publish()
        info = U.check()
        entry = dict(info.files["tgz"], version="9.9.8")
        with self.assertRaises(U.UpdateError):
            U.verify_entry(entry)

    def test_foreign_host_rejected(self):
        self.publish(url="https://example.com/p.tar.gz")
        info = U.check()
        with self.assertRaises(U.UpdateError):
            U.download(info.files["tgz"], tempfile.mkdtemp())

    def test_corrupted_download_rejected(self):
        self.publish(sha="0" * 64)
        info = U.check()
        out = tempfile.mkdtemp()
        with self.assertRaises(U.UpdateError):
            U.download(info.files["tgz"], out)
        self.assertEqual(os.listdir(out), [])

    def test_unpublished(self):
        self.publish(version="")
        with self.assertRaises(U.UpdateError):
            U.check()

    def test_versions_and_scheme(self):
        self.assertTrue(U.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(U.is_newer("1.3.0", "1.3.0"))
        with self.assertRaises(U.UpdateError):
            U._check_scheme("http://www.pt2vhf.com/x")


class ExtractTests(unittest.TestCase):
    def test_rejects_path_traversal(self):
        import tarfile
        d = tempfile.mkdtemp()
        evil = os.path.join(d, "evil.tar.gz")
        src = os.path.join(d, "x.txt")
        with open(src, "w") as fh:
            fh.write("x")
        with tarfile.open(evil, "w:gz") as t:
            t.add(src, arcname="../../fora.txt")
        with self.assertRaises(U.UpdateError):
            U._extract(evil, os.path.join(d, "out"))

    def test_extracts_single_root(self):
        import tarfile
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "app-1.0"))
        with open(os.path.join(d, "app-1.0", "main.py"), "w") as fh:
            fh.write("print(1)")
        arc = os.path.join(d, "a.tar.gz")
        with tarfile.open(arc, "w:gz") as t:
            t.add(os.path.join(d, "app-1.0"), arcname="app-1.0")
        root = U._extract(arc, os.path.join(d, "out"))
        self.assertTrue(os.path.isfile(os.path.join(root, "main.py")))


if __name__ == "__main__":
    unittest.main()
