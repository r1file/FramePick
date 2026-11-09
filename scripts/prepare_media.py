"""Stage pinned, hash-verified LGPL tools. No installation or PATH changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(*, archive: Path | None = None, from_system=False):
    manifest = json.loads((ROOT / "packaging/media-tools.json").read_text(encoding="utf-8"))
    key = f"{platform.system().lower()}-{platform.machine().lower()}"
    vendor = ROOT / "vendor"
    binaries = vendor / "bin"
    licenses = vendor / "licenses"
    binaries.mkdir(parents=True, exist_ok=True)
    licenses.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if sys.platform == "win32" else ""
    if from_system:
        provenance = {"provider": "local system", "platform": key}
        for tool in ("ffmpeg", "ffprobe"):
            found = shutil.which(tool)
            if not found:
                raise SystemExit(f"Missing local {tool}")
            shutil.copy2(found, binaries / f"{tool}{suffix}")
        provenance["source_information"] = (
            "Local build: retain its provider's source/build and license materials."
        )
    else:
        if key not in manifest["platforms"]:
            raise SystemExit(
                "No pinned build for this platform; explicitly stage local tools with --from-system."
            )
        config = manifest["platforms"][key]
        notice = vendor / "NOTICE.txt"
        if archive is None and notice.is_file():
            previous = json.loads(notice.read_text(encoding="utf-8"))
            if previous.get("sha256") == config["sha256"]:
                verified = True
                for name, expected in previous.get("binary_sha256", {}).items():
                    path = binaries / name
                    if not path.is_file():
                        verified = False
                        break
                    with path.open("rb") as stream:
                        verified &= hashlib.file_digest(stream, "sha256").hexdigest() == expected
                if verified and len(previous.get("binary_sha256", {})) == 2:
                    print("Using verified staged FFmpeg tools")
                    return
        cache = ROOT / "artifacts/downloads"
        cache.mkdir(parents=True, exist_ok=True)
        if archive is None:
            archive = cache / config["url"].rsplit("/", 1)[1]
            if not archive.is_file():
                print(f"Downloading {config['url']}", flush=True)
                urllib.request.urlretrieve(config["url"], archive)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != config["sha256"]:
            raise SystemExit(f"Media tools checksum mismatch: {archive}")
        provenance = {
            **config,
            "provider": manifest["provider"],
            "release": manifest["release"],
            "source_revision": manifest["upstream_revision"],
            "source_url": f"https://github.com/FFmpeg/FFmpeg/tree/{manifest['upstream_revision']}",
            "build_recipe": manifest["recipe_url"],
            "platform": key,
        }

        def copy_member(name, read):
            path = Path(name)
            lower = name.lower()
            if path.name in (f"ffmpeg{suffix}", f"ffprobe{suffix}"):
                (binaries / path.name).write_bytes(read())
                (binaries / path.name).chmod(0o755)
            elif any(
                part in lower for part in ("license", "copying", "readme")
            ) and not lower.endswith("/"):
                # Flatten trusted notice names; never extract arbitrary archive paths.
                target = licenses / path.name
                target.write_bytes(read())

        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as package:
                for item in package.infolist():
                    if not item.is_dir():
                        copy_member(item.filename, lambda i=item: package.read(i))
        else:
            with tarfile.open(archive, "r:*") as package:
                for item in package.getmembers():
                    if item.isfile():

                        def read(member=item):
                            with package.extractfile(member) as stream:
                                return stream.read()

                        copy_member(item.name, read)
    hashes = {}
    for tool in ("ffmpeg", "ffprobe"):
        path = binaries / f"{tool}{suffix}"
        if not path.is_file():
            raise SystemExit(f"Archive did not contain {path.name}")
        with path.open("rb") as stream:
            hashes[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    result = subprocess.run(
        [str(binaries / f"ffmpeg{suffix}"), "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    provenance["binary_sha256"] = hashes
    provenance["version_and_configuration"] = result.stdout
    (vendor / "NOTICE.txt").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(result.stdout.splitlines()[0])
    print(f"Staged tools and notices in {vendor}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive", type=Path, help="Use an already downloaded archive (hash is still verified)"
    )
    parser.add_argument(
        "--from-system",
        action="store_true",
        help="Explicitly stage local tools, e.g. macOS development builds",
    )
    args = parser.parse_args()
    prepare(archive=args.archive, from_system=args.from_system)
