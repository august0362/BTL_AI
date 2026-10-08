"""Run one bot in its own process so the operating system measures its memory.

The OS keeps the peak resident memory of every process for free, so measuring it does not
slow the bot down. A worker process records its baseline memory (Python, python-chess,
the registry), creates the bot, plays the moves it is asked for, and on ``close`` reports
``peak - baseline``: the memory the bot needed (its own module, weights and tables, plus
temporary search structures such as caches and trees, even when freed before the move).
Thinking time is measured inside the worker, so the inter-process round trip is not charged
to the bot.
"""

from __future__ import annotations

import ctypes
import gc
import multiprocessing
import sys
import time

import chess

_CONTEXT = multiprocessing.get_context("spawn")
_POLL_S = 0.2
_START_TIMEOUT_S = 120.0
_CLOSE_TIMEOUT_S = 10.0


def memory_usage() -> tuple[int, int]:
    """Return (current, peak) resident memory of this process in bytes."""
    if sys.platform == "win32":
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

        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_Counters),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), counters, counters.cb)
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak *= 1 if sys.platform == "darwin" else 1024
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
        import os

        current = pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        current = peak
    return current, peak


def _worker(conn, bot_id: str, config: dict) -> None:
    """Child process: create the bot, then answer move/reset/stop requests.

    The baseline is taken before the bot exists, so everything the bot brings (its module,
    libraries, weights, tables) plus all memory used while thinking counts as its memory.
    """
    from ai import registry

    gc.collect()
    baseline, _ = memory_usage()
    try:
        bot = registry.create_bot(bot_id, config)
    except Exception as exc:  # noqa: BLE001 - reported to the parent, which records it
        conn.send(("error", str(exc)))
        conn.close()
        return
    conn.send(("ready", bot.display_name))
    while True:
        message = conn.recv()
        kind = message[0]
        if kind == "move":
            board = chess.Board(message[1])
            for uci in message[2]:
                board.push_uci(uci)
            try:
                started = time.perf_counter()
                move = bot.select_move(board)
                think = time.perf_counter() - started
            except Exception as exc:  # noqa: BLE001 - the parent aborts the game
                conn.send(("error", str(exc)))
                continue
            info = dict(getattr(bot, "last_search_info", {}) or {})
            conn.send(("move", move.uci(), think, info))
        elif kind == "reset":
            try:
                bot.reset()
                conn.send(("ok",))
            except Exception as exc:  # noqa: BLE001
                conn.send(("error", str(exc)))
        else:  # "stop"
            _, peak = memory_usage()
            conn.send(("memory", max(0, peak - baseline)))
            conn.close()
            return


class ProcessPlayer:
    """A tournament player whose bot lives in a separate process (one per game)."""

    def __init__(self, bot_id: str, config: dict | None = None) -> None:
        self.bot_id = bot_id
        self.display_name = bot_id
        self.last_search_info: dict = {}
        self.measured_think_time_s: float | None = None
        self.memory_bytes: int | None = None
        parent, child = _CONTEXT.Pipe()
        self._conn = parent
        self._process = _CONTEXT.Process(
            target=_worker, args=(child, bot_id, dict(config or {})), daemon=True
        )
        self._process.start()
        child.close()
        try:
            reply = self._receive(_START_TIMEOUT_S)
        except Exception:
            self._kill()
            raise
        if reply[0] == "error":
            self._kill()
            raise RuntimeError(reply[1])
        self.display_name = reply[1]

    def select_move(self, board: chess.Board) -> chess.Move:
        """Ask the worker for a move; its own clock gives the thinking time."""
        root = board.root()
        self._conn.send(("move", root.fen(), [move.uci() for move in board.move_stack]))
        reply = self._receive(None)
        if reply[0] == "error":
            raise RuntimeError(reply[1])
        _, uci, think, info = reply
        self.measured_think_time_s = float(think)
        self.last_search_info = info
        return chess.Move.from_uci(uci)

    def reset(self) -> None:
        """Reset the bot inside the worker."""
        self._conn.send(("reset",))
        reply = self._receive(_START_TIMEOUT_S)
        if reply[0] == "error":
            raise RuntimeError(reply[1])

    def close(self) -> int | None:
        """Stop the worker and return the bot's peak extra memory in bytes (None if lost)."""
        if not self._process.is_alive():
            self._kill()
            return self.memory_bytes
        try:
            self._conn.send(("stop",))
            reply = self._receive(_CLOSE_TIMEOUT_S)
            if reply[0] == "memory":
                self.memory_bytes = int(reply[1])
        except (OSError, EOFError, RuntimeError, TimeoutError):
            pass
        finally:
            self._kill()
        return self.memory_bytes

    def _receive(self, timeout_s: float | None):
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while not self._conn.poll(_POLL_S):
            if not self._process.is_alive():
                raise RuntimeError(f"{self.bot_id}: bot process exited")
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError(f"{self.bot_id}: bot process did not answer")
        return self._conn.recv()

    def _kill(self) -> None:
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=_CLOSE_TIMEOUT_S)
        self._conn.close()
