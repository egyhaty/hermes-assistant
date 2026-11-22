"""Install the integrity-pinned official native client bundle, including its companion host."""
import argparse
import base64
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath


def install(release, destination):
    meta = json.loads(Path(release).read_text())
    if not meta['tarball'].startswith('https://registry.npmjs.org/@openai/codex/-/'):
        raise ValueError('Unexpected client publisher')
    with urllib.request.urlopen(meta['tarball'], timeout=90) as response:
        payload = response.read()
    algorithm, expected = meta['integrity'].split('-', 1)
    if algorithm != 'sha512' or base64.b64encode(hashlib.sha512(payload).digest()).decode() != expected:
        raise ValueError('Official client integrity check failed')
    root = Path(destination); root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] != 'package':
                raise ValueError('Unsafe client archive path')
            relative = Path(*name.parts[1:])
            if member.isdir():
                (root / relative).mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            else:
                raise ValueError('Unexpected client archive link')
    def is_native(path):
        if not path.is_file(): return False
        with path.open('rb') as stream: return stream.read(4) == b'\x7fELF'
    binaries = [p for p in root.rglob('codex') if is_native(p)]
    if len(binaries) != 1:
        raise ValueError('Expected one official native client')
    links = root / 'bin'; links.mkdir(exist_ok=True)
    for binary in binaries[0].parent.iterdir():
        if binary.is_file() and binary.stat().st_mode & 0o111:
            target = links / binary.name
            if target != binary and not target.exists(): target.symlink_to(binary.resolve())
    (root / 'release.json').write_text(json.dumps(meta, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True); parser.add_argument('--destination', required=True)
    args = parser.parse_args(); install(args.release, args.destination)
