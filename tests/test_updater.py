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
        os.environ["PT2VHF_UPDATE_URL"] = self.base + "atualizacao.json"
        self.orig_key = U.PUBLIC_KEY
        U.PUBLIC_KEY = PUB

    def tearDown(self):
        self.srv.shutdown()
        U.PUBLIC_KEY = self.orig_key
        os.environ.pop("PT2VHF_UPDATE_URL", None)

    def publish(self, sha=None, key=KEY, tamper=False):
        m = {"app": U.APP_ID, "version": "9.9.9", "notes": ["x"],
             "files": {"tgz": {"file": "p.tar.gz", "sha256": sha or
                               hashlib.sha256(self.payload).hexdigest()}}}
        data = json.dumps(m).encode()
        sig = ed25519.sign(key, data)
        if tamper:
            data = data.replace(b"9.9.9", b"9.9.8")
        with open(os.path.join(self.dir, "atualizacao.json"), "wb") as fh:
            fh.write(data)
        with open(os.path.join(self.dir, "atualizacao.json.sig"), "w") as fh:
            fh.write(base64.b64encode(sig).decode())

    def test_check_and_download(self):
        self.publish()
        info = U.check()
        self.assertTrue(U.is_newer(info.version, "1.3.0"))
        out = tempfile.mkdtemp()
        path = U.download(info.files["tgz"], out)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), self.payload)

    def test_bad_signature_rejected(self):
        self.publish(tamper=True)
        with self.assertRaises(U.UpdateError):
            U.check()
        self.publish(key=bytes(32))         # outra chave
        with self.assertRaises(U.UpdateError):
            U.check()

    def test_corrupted_download_rejected(self):
        self.publish(sha="0" * 64)
        info = U.check()
        out = tempfile.mkdtemp()
        with self.assertRaises(U.UpdateError):
            U.download(info.files["tgz"], out)
        self.assertEqual(os.listdir(out), [])

    def test_versions_and_scheme(self):
        self.assertTrue(U.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(U.is_newer("1.3.0", "1.3.0"))
        with self.assertRaises(U.UpdateError):
            U._check_scheme("http://www.pt2vhf.com/x")


if __name__ == "__main__":
    unittest.main()
