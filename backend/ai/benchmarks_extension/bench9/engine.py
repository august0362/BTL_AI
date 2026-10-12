"""UCI process management for Benchmark 9 (python-chess ``SimpleEngine`` underneath)."""

from __future__ import annotations

import atexit
import ctypes
import subprocess
import sys
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine

INFO = chess.engine.INFO_BASIC | chess.engine.INFO_SCORE
_LIVE: weakref.WeakSet[UciEngine] = weakref.WeakSet()


def close_all() -> None:
    """Close every running engine (at exit: their event-loop threads are not daemons)."""
    for engine in list(_LIVE):
        engine.close()


# Runs before the interpreter waits for non-daemon threads, so an open engine cannot hang exit.
_register = getattr(threading, "_register_atexit", atexit.register)
_register(close_all)


class EngineError(Exception):
    """The engine process failed to start, crashed, hung or answered nonsense."""


@dataclass(frozen=True)
class EngineSettings:
    """How to launch and configure one engine process."""

    path: Path
    args: tuple[str, ...] = ()  # extra command line arguments (tests run fake engines)
    threads: int = 1
    hash_mb: int = 16
    nnue_path: Path | None = None  # None = the network embedded in the binary
    syzygy_path: str | None = None
    init_timeout_s: float = 20.0
    hard_margin_s: float = 1.0  # a search answering later than limit + this is a hang


class UciEngine:
    """One engine process: start, search with a hard deadline, report memory, close."""

    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings
        self.name = ""
        self.network = ""  # NNUE file the engine reported loading ("" if it did not say)
        self._engine: chess.engine.SimpleEngine | None = None
        self._pid: int | None = None
        self._peak_bytes = 0

    def start(self) -> None:
        """Launch the process, apply the options and wait until it is ready."""
        self.close()
        popen_args = {}
        if sys.platform == "win32":
            popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            engine = chess.engine.SimpleEngine.popen_uci(
                [str(self.settings.path), *self.settings.args],
                timeout=self.settings.init_timeout_s,
                **popen_args,
            )
        except (TimeoutError, OSError, chess.engine.EngineError) as exc:
            raise EngineError(f"could not start {self.settings.path}: {exc}") from exc
        self._engine = engine
        self._pid = engine.transport.get_pid()
        _LIVE.add(self)
        try:
            engine.configure(self._options(engine))
            engine.ping()
        except (TimeoutError, chess.engine.EngineError, OSError, ValueError) as exc:
            self.kill()
            raise EngineError(f"engine rejected its options: {exc}") from exc
        self.name = str(engine.id.get("name", ""))
        self.network = self._probe_network(engine)

    def _probe_network(self, engine: chess.engine.SimpleEngine) -> str:
        """Run a depth-1 search: the engine loads (or rejects) its network on the first go."""
        strings: list[str] = []
        try:
            with engine.analysis(chess.Board(), chess.engine.Limit(depth=1)) as analysis:
                for info in analysis:
                    if "string" in info:
                        strings.append(str(info["string"]))
        except (TimeoutError, chess.engine.EngineError, OSError) as exc:
            self.kill()
            detail = "; ".join(s for s in strings if "ERROR" in s) or repr(exc)
            raise EngineError(f"engine failed its first search: {detail}") from exc
        errors = [s for s in strings if "ERROR" in s]
        if errors or not self.alive:
            self.kill()
            raise EngineError("; ".join(errors) or "engine exited during its first search")
        for text in strings:
            if text.startswith("NNUE evaluation using "):
                return text.removeprefix("NNUE evaluation using ").split(" ")[0]
        return ""

    def _options(self, engine: chess.engine.SimpleEngine) -> dict[str, object]:
        options: dict[str, object] = {}
        wanted: dict[str, object] = {
            "Threads": self.settings.threads,
            "Hash": self.settings.hash_mb,
        }
        if self.settings.nnue_path is not None:
            wanted["EvalFile"] = str(self.settings.nnue_path)
        if self.settings.syzygy_path:
            wanted["SyzygyPath"] = self.settings.syzygy_path
        for name, value in wanted.items():
            if name in engine.options:
                options[name] = value
            elif name in ("EvalFile", "SyzygyPath"):
                raise ValueError(f"engine has no {name} option")
        return options

    @property
    def alive(self) -> bool:
        """True while the process is running."""
        if self._engine is None:
            return False
        try:
            return self._engine.transport.get_returncode() is None
        except Exception:  # noqa: BLE001 - a closed transport counts as dead
            return False

    def search(
        self, board: chess.Board, limit: chess.engine.Limit, game: object
    ) -> chess.engine.PlayResult:
        """Search ``board`` (sent with its whole move history); EngineError on any failure."""
        engine = self._engine
        if engine is None or not self.alive:
            raise EngineError("engine process is not running")
        engine.timeout = self.settings.hard_margin_s  # deadline = limit.time + this
        try:
            result = engine.play(board, limit, game=game, info=INFO)
        except (chess.engine.EngineError, TimeoutError, OSError) as exc:  # incl. terminated
            self.kill()
            raise EngineError(f"search failed: {exc!r}") from exc
        if result.move is None or result.move not in board.legal_moves:
            self.kill()
            raise EngineError(f"engine returned an illegal move: {result.move}")
        return result

    def peak_memory_bytes(self) -> int:
        """Largest resident memory the engine processes of this object have used."""
        if self._pid is not None and self.alive:
            self._peak_bytes = max(self._peak_bytes, process_peak_memory(self._pid))
        return self._peak_bytes

    def close(self) -> None:
        """Quit the process politely, killing it if it does not answer."""
        engine = self._engine
        if engine is None:
            return
        self.peak_memory_bytes()
        try:
            engine.timeout = 2.0
            engine.quit()
        except Exception:  # noqa: BLE001 - fall back to killing the process
            pass
        self.kill()

    def kill(self) -> None:
        """Terminate the process immediately and stop the event loop thread."""
        engine, self._engine = self._engine, None
        _LIVE.discard(self)
        if engine is None:
            return
        try:
            transport = engine.transport
            if transport.get_returncode() is None:
                transport.kill()
        except Exception:  # noqa: BLE001 - already gone
            pass
        try:
            engine.close()
        except Exception:  # noqa: BLE001
            pass


def process_peak_memory(pid: int) -> int:
    """Peak resident memory of another process in bytes (0 when it cannot be read)."""
    if sys.platform == "win32":
        return _windows_peak_memory(pid)
    try:
        with open(f"/proc/{pid}/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _windows_peak_memory(pid: int) -> int:
    size_t = ctypes.c_size_t

    class _Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", size_t),
            ("WorkingSetSize", size_t),
            ("QuotaPeakPagedPoolUsage", size_t),
            ("QuotaPagedPoolUsage", size_t),
            ("QuotaPeakNonPagedPoolUsage", size_t),
            ("QuotaNonPagedPoolUsage", size_t),
            ("PagefileUsage", size_t),
            ("PeakPagefileUsage", size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_Counters),
        ctypes.c_ulong,
    ]
    handle = kernel32.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return 0
    try:
        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.PeakWorkingSetSize)
    finally:
        kernel32.CloseHandle(handle)
