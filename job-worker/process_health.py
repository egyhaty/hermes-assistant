"""Recover stale X11 state without touching a running display or browser profile."""
import os
import socket
import stat
import time
from pathlib import Path


def display_responds(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(0.5)
        try:
            client.connect(str(path))
            return True
        except (FileNotFoundError, ConnectionRefusedError):
            return False


def process_alive(pid):
    if pid <= 0:
        raise ValueError('Invalid display lock PID')
    try:
        # A dead child can retain its PID until the parent reaps it.
        status = Path(f'/proc/{pid}/stat')
        try:
            if status.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                return False
        except FileNotFoundError:
            pass
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def clean_stale_display(tmp=Path('/tmp'), display=99):
    lock = tmp / f'.X{display}-lock'
    endpoint = tmp / '.X11-unix' / f'X{display}'
    if display_responds(endpoint):
        raise RuntimeError(f'Display :{display} is active; refusing to remove its lock')
    if lock.exists():
        if lock.is_symlink():
            raise RuntimeError('Refusing a symlinked X11 lock')
        try:
            pid = int(lock.read_text().strip())
        except ValueError as error:
            raise RuntimeError('Invalid X11 lock; manual inspection required') from error
        if process_alive(pid):
            raise RuntimeError(f'Display lock owner {pid} is alive; refusing cleanup')
    # Only this worker UID's two stale display files can be removed.
    for path in (lock, endpoint):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if info.st_uid != os.getuid() or stat.S_ISDIR(info.st_mode):
            raise RuntimeError(f'Refusing to remove unowned X11 state: {path.name}')
        path.unlink()
        print(f'Removed stale X11 state: {path.name}', flush=True)


def wait_for_display(proc, endpoint=Path('/tmp/.X11-unix/X99'), timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f'Xvfb exited during startup: {proc.returncode}')
        if display_responds(endpoint):
            return
        time.sleep(0.1)
    raise RuntimeError('Xvfb did not become ready within the startup deadline')


def failed_children(procs):
    return [{'name': Path(proc.args[0]).name, 'exit_code': code}
            for proc in procs if (code := proc.poll()) is not None]
