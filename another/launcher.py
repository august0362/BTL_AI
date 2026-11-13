"""Start the game for run.bat: update model checkpoints, then run main.py until its window closes.

Checkpoints come from the newest GitHub release tagged ``models-*`` (asset ``models.json``). A
checkpoint is downloaded only when missing or changed, checked against its SHA-256 and moved into
place atomically. The applied manifest is kept in ``backend/config/models.json``; its ``config``
table is merged into the game configuration (core.config). Without network the last verified
checkpoints are used. On Windows the game then runs in a detached windowless process (pythonw,
output in .runtime/game.log), so run.bat's console closes as soon as the game opens; that process
holds a job object, so closing the game window stops every process it started.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = "august0362/BTL_AI"
MODEL_FORMAT = 1  # manifests with another format need a newer app
LOCAL_MANIFEST = ROOT / "backend" / "config" / "models.json"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
TIMEOUT_S = 15


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "BTL_AI-launcher"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read()


def fetch_remote_manifest(api_url: str = RELEASES_API) -> dict[str, Any]:
    """Return the manifest of the newest published ``models-*`` release."""
    for release in json.loads(_get(api_url)):
        if release.get("draft") or release.get("prerelease"):
            continue
        if not str(release.get("tag_name", "")).startswith("models-"):
            continue
        for asset in release.get("assets", []):
            if asset.get("name") == "models.json":
                return json.loads(_get(asset["browser_download_url"]))
    raise LookupError("no models-* release with models.json")


def read_manifest(path: Path = LOCAL_MANIFEST) -> dict[str, Any] | None:
    """Return the last applied manifest, or None."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def asset_path(asset: dict[str, Any], root: Path = ROOT) -> Path:
    """Where an asset lives; only ``backend/ai/<bot>/weights/`` is allowed."""
    path = (root / asset["dir"] / asset["name"]).resolve()
    allowed = (root / "backend" / "ai").resolve()
    if allowed not in path.parents or path.parent.name != "weights":
        raise ValueError(f"unsafe asset path: {asset['dir']}/{asset['name']}")
    return path


def is_valid(asset: dict[str, Any], root: Path = ROOT) -> bool:
    """True when the asset file exists with the expected size and SHA-256."""
    path = asset_path(asset, root)
    return (
        path.is_file()
        and path.stat().st_size == int(asset["size"])
        and sha256_file(path) == asset["sha256"].lower()
    )


def download(asset: dict[str, Any], root: Path = ROOT) -> None:
    """Download to a temporary file, verify, then atomically replace the target."""
    path = asset_path(asset, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".download")
    try:
        request = urllib.request.Request(asset["url"], headers={"User-Agent": "BTL_AI-launcher"})
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            with temporary.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
        if temporary.stat().st_size != int(asset["size"]):
            raise ValueError(f"{asset['name']}: incomplete download")
        if sha256_file(temporary) != asset["sha256"].lower():
            raise ValueError(f"{asset['name']}: SHA-256 mismatch")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_manifest(manifest: dict[str, Any], root: Path = ROOT) -> int:
    """Make every asset of the manifest present and valid; return how many were downloaded."""
    downloaded = 0
    for asset in manifest["assets"]:
        if is_valid(asset, root):
            continue
        mb = int(asset["size"]) / 1e6
        print(f"  Đang tải {asset['name']} ({mb:.1f} MB)...", flush=True)
        download(asset, root)
        downloaded += 1
    return downloaded


def save_manifest(manifest: dict[str, Any], path: Path = LOCAL_MANIFEST) -> None:
    """Write the applied manifest atomically."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def update_models(
    fetch: Any = fetch_remote_manifest, root: Path = ROOT, local_path: Path = LOCAL_MANIFEST
) -> bool:
    """Bring checkpoints up to date; return False only if no usable checkpoints exist."""
    local = read_manifest(local_path)
    try:
        remote = fetch()
    except Exception as exc:  # offline, GitHub down, rate limit...
        print(f"  Không kiểm tra được bản model mới ({exc}).", flush=True)
        remote = None
    if remote is not None and remote.get("format") != MODEL_FORMAT:
        print("  Có model mới nhưng cần bản ứng dụng mới hơn; giữ model hiện tại.", flush=True)
        remote = None
    if remote is not None:
        try:
            count = apply_manifest(remote, root)
            if remote != local:
                save_manifest(remote, local_path)
            state = f"đã cập nhật {count} file" if count else "đã là bản mới nhất"
            print(f"  Model {remote['version']}: {state}.", flush=True)
            return True
        except Exception as exc:
            print(f"  Cập nhật model lỗi ({exc}); dùng bản đã kiểm tra trước đó.", flush=True)
    if local is not None and all(is_valid(asset, root) for asset in local["assets"]):
        print(f"  Dùng model {local['version']} đã có trên máy.", flush=True)
        return True
    return False


def _kill_on_close_job() -> None:
    """Put this process in a job whose processes all die when the job's last handle closes."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class Limits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", Limits),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    info = ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = job and kernel32.SetInformationJobObject(
        wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info)
    )
    ok = ok and kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(job), wintypes.HANDLE(kernel32.GetCurrentProcess())
    )
    if not ok:
        print("  (Không tạo được job object; tiến trình con có thể còn chạy sau khi đóng.)")
    # The handle stays open until this process exits; then Windows kills the whole job.


GAME_LOG = ROOT / ".runtime" / "game.log"
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
BREAKAWAY = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB


def run_game() -> int:
    """Run main.py inside a kill-on-close job, logging its output; return its exit code."""
    _kill_on_close_job()
    GAME_LOG.parent.mkdir(exist_ok=True)
    with GAME_LOG.open("w", encoding="utf-8") as log:
        return subprocess.call(
            [sys.executable, str(ROOT / "main.py")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
        )


def start_detached() -> None:
    """Start ``run_game`` in a windowless process that outlives this console."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    command = [str(pythonw if pythonw.is_file() else sys.executable), __file__, "--run-game"]
    try:
        subprocess.Popen(command, cwd=ROOT, creationflags=DETACHED | BREAKAWAY, close_fds=True)
    except OSError:  # the console's job may forbid breakaway; then just detach
        subprocess.Popen(command, cwd=ROOT, creationflags=DETACHED, close_fds=True)


def main() -> int:
    """Update models, then start the game (detached on Windows) and return an exit code."""
    if "--run-game" in sys.argv[1:]:
        return run_game()
    print("[3/4] Kiểm tra model AI...", flush=True)
    if not update_models():
        print("LỖI: Chưa có model AI và không tải được. Hãy kết nối Internet rồi chạy lại run.bat.")
        return 1
    if os.name != "nt":
        print("[4/4] Mở game. Đóng cửa sổ game để thoát hoàn toàn.", flush=True)
        return subprocess.call([sys.executable, str(ROOT / "main.py")], cwd=ROOT)
    print("[4/4] Mở game... (cửa sổ này tự đóng; lỗi của game ghi ở .runtime/game.log)", flush=True)
    start_detached()
    return 0


if __name__ == "__main__":
    sys.exit(main())
