"""Build a read-only summary of configured model weights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from gui.i18n import Translator


@dataclass(frozen=True)
class WeightsRow:
    """Describe the configured weights for one bot."""

    bot_id: str
    name: str
    file: str
    source: str
    sha256: str
    depth: str


def weights_rows(config: dict[str, Any], translator: Translator) -> list[WeightsRow]:
    """Return configured weights rows in bot configuration order."""
    rows = []
    for bot_id, table in config.get("bots", {}).items():
        if not isinstance(table, dict) or "weights_url" not in table:
            continue
        if table.get("enabled", True) is False:
            continue
        url = str(table.get("weights_url") or "")
        parsed = urlsplit(url)
        file_name = unquote(parsed.path.rsplit("/", 1)[-1]) if url else ""
        if not url:
            file_name = translator.t("settings.weights_none")
            source = ""
        elif parsed.scheme.lower() == "file":
            source = translator.t("settings.weights_local")
        elif parsed.scheme.lower() in {"http", "https"}:
            source = translator.t("settings.weights_release")
        else:
            source = ""
        name = table.get("display_name") or translator.t(f"players.{bot_id}")
        rows.append(
            WeightsRow(
                bot_id=bot_id,
                name=str(name),
                file=file_name,
                source=source,
                sha256=str(table.get("weights_sha256", ""))[:8],
                depth=str(table.get("depth", 3)),
            )
        )
    return rows
