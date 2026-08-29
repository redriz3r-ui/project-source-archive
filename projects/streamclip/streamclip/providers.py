from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from .models import ChatMessage


class Provider(ABC):
    name = "generic"

    @abstractmethod
    def matches(self, url: str) -> bool: ...

    def download_video(self, url: str, output_dir: Path, quality: str) -> Path:
        output = output_dir / "source.%(ext)s"
        cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", quality,
               "--merge-output-format", "mp4", "-o", str(output), url]
        _run(cmd, "video download (install yt-dlp)")
        files = sorted(output_dir.glob("source.*"))
        if not files:
            raise RuntimeError("Downloader completed but no source video was created")
        return files[0]

    def download_chat(self, url: str, output_dir: Path) -> Path:
        output = output_dir / "chat.json"
        cmd = [sys.executable, "-m", "chat_downloader", url, "--output", str(output),
               "--message_groups", "messages"]
        _run(cmd, "chat download (install chat-downloader)")
        return output

    def parse_chat(self, path: Path) -> list[ChatMessage]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            # chat-downloader uses a top-level list/messages field, while
            # TwitchDownloaderCLI exports Twitch's native `comments` objects.
            raw = raw.get("messages", raw.get("items", raw.get("comments", [])))
        messages = []
        for item in raw:
            ts = item.get("time_in_seconds", item.get("content_offset_seconds",
                          item.get("timestamp", item.get("time", 0))))
            if isinstance(ts, str):
                ts = _parse_time(ts)
            author = item.get("author", item.get("commenter", {}))
            if isinstance(author, dict):
                author = author.get("id") or author.get("_id") or author.get("name") or ""
            text = item.get("message", item.get("text", ""))
            if isinstance(text, dict):
                text = text.get("body", "")
            if isinstance(text, list):
                text = "".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in text)
            messages.append(ChatMessage(float(ts or 0), str(author), str(text)))
        return sorted(messages, key=lambda m: m.timestamp)


class TwitchProvider(Provider):
    name = "twitch"
    def matches(self, url: str) -> bool:
        return "twitch.tv" in urlparse(url).netloc.lower()

    def download_chat(self, url: str, output_dir: Path) -> Path:
        try:
            return super().download_chat(url, output_dir)
        except RuntimeError as primary_error:
            binary = os.environ.get("STREAMCLIP_TWITCH_DOWNLOADER") or shutil.which("TwitchDownloaderCLI")
            if not binary:
                raise RuntimeError(
                    f"Primary Twitch chat download failed and TwitchDownloaderCLI was not found: {primary_error}. "
                    "Install TwitchDownloaderCLI or set STREAMCLIP_TWITCH_DOWNLOADER to its path."
                ) from primary_error
            match = re.search(r"/videos/(\d+)", url)
            if not match:
                raise ValueError("A Twitch VOD URL containing /videos/ID is required")
            output = output_dir / "chat.json"
            _run([binary, "chatdownload", "--id", match.group(1), "--output", str(output)],
                 "TwitchDownloaderCLI chat fallback")
            return output


class YouTubeProvider(Provider):
    name = "youtube"
    def matches(self, url: str) -> bool:
        return any(x in urlparse(url).netloc.lower() for x in ("youtube.com", "youtu.be"))


class KickProvider(Provider):
    name = "kick"
    def matches(self, url: str) -> bool:
        return "kick.com" in urlparse(url).netloc.lower()


class GenericProvider(Provider):
    name = "generic"
    def matches(self, url: str) -> bool:
        return True


PROVIDERS = [TwitchProvider(), YouTubeProvider(), KickProvider(), GenericProvider()]


def provider_for(url: str) -> Provider:
    return next(p for p in PROVIDERS if p.matches(url))


def _parse_time(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        parts = value.split(":")
        return sum(float(v) * (60 ** i) for i, v in enumerate(reversed(parts)))


def _run(cmd: list[str], purpose: str) -> None:
    try:
        subprocess.run(cmd, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(f"Failed during {purpose}: {exc}") from exc
