"""Exercise GoFile's actual packaged Node and resolver with no Node on PATH.

Run: python tests/packaged_gofile_smoke.py dist/buidl.exe
This uses a synthetic website script and performs no network requests.
"""

import os
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory

from PyInstaller.archive.readers import CArchiveReader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(executable):
    archive = CArchiveReader(str(executable))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    with TemporaryDirectory(prefix="buidl-gofile-") as folder:
        bundle = Path(folder)
        node_entry = next(name for name in archive.toc if name.lower() == "node.exe")
        (bundle / "node.exe").write_bytes(archive.extract(node_entry))
        assert any(name.replace("\\", "/") == "licenses/node/LICENSE" for name in archive.toc)
        module = types.ModuleType("packaged_resolvers")
        sys.modules[module.__name__] = module
        exec(pyz.extract("src.resolvers"), module.__dict__)
        previous_path = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = ""
            sys._MEIPASS = folder
            source = "function _sha256(x){return x;} function generateWT(t){return _sha256('probe::en-US::'+t+'::123::bundled_salt123');}"
            client = types.SimpleNamespace(timeout=10, get=lambda *args, **kwargs: types.SimpleNamespace(text=source))
            assert module._discover_gofile_salt(client, force=True) == "bundled_salt123"
            print("PACKAGED GOFILE PASS: bundled Node executes website script with empty PATH")
        finally:
            os.environ["PATH"] = previous_path
            del sys._MEIPASS
            del sys.modules[module.__name__]


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(strict=True))
