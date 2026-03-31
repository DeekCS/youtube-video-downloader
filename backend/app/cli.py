"""Command-line interface: list formats and download with a chosen format."""

from __future__ import annotations

import argparse
import json
import sys

from app.models.video import Format, VideoInfo
from app.services.errors import (
    FormatNotAvailableError,
    InvalidUrlError,
    UnsupportedPlatformError,
    VideoNotFoundError,
    YtdlpFailedError,
)
from app.services.yt_dlp_service import FORMAT_ID_PATTERN, YtDlpService


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _format_size(filesize_bytes: int | None) -> str:
    if not filesize_bytes:
        return "-"
    mb = filesize_bytes / (1024 * 1024)
    return f"{mb:.1f} MiB"


def _kind_label(fmt: Format) -> str:
    if fmt.is_audio_only:
        return "audio"
    if fmt.is_video_only:
        return "video-only"
    ql = fmt.quality_label.lower()
    if "merged" in ql or "best available" in ql:
        return "merged"
    return "muxed"


def cmd_formats(url: str, as_json: bool) -> int:
    try:
        info = YtDlpService.fetch_formats(url)
    except (InvalidUrlError, UnsupportedPlatformError) as e:
        _err(str(e))
        return 2
    except VideoNotFoundError:
        _err("Video not found.")
        return 1
    except FormatNotAvailableError as e:
        _err(str(e))
        return 1
    except YtdlpFailedError as e:
        _err(str(e))
        return 1

    if as_json:
        print(json.dumps(info.model_dump(mode="json"), indent=2))
        return 0

    vid = info.video_id or "?"
    print(f"Title: {info.title}")
    print(f"Video id: {vid}\n")
    print(f"{'#':<5} {'ID':<14} {'Quality':<26} {'Kind':<10} {'Size':<10}")
    print("-" * 78)
    for i, f in enumerate(info.formats, start=1):
        fid = f.id if len(f.id) <= 40 else f.id[:37] + "..."
        q = f.quality_label if len(f.quality_label) <= 24 else f.quality_label[:21] + "..."
        print(
            f"{i:<5} {fid:<14} {q:<26} {_kind_label(f):<10} "
            f"{_format_size(f.filesize_bytes):<10}"
        )
    return 0


def _resolve_format_choice(
    info: VideoInfo,
    choice: str,
) -> str | None:
    choice = choice.strip()
    if not choice:
        return None
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(info.formats):
            return info.formats[idx - 1].id
        return None
    if FORMAT_ID_PATTERN.match(choice):
        return choice
    return None


def _interactive_format(info: VideoInfo) -> str:
    print(f"Title: {info.title}\n")
    for i, f in enumerate(info.formats, start=1):
        print(f"  {i:>3}  {f.id}")
        print(f"       {f.quality_label}  ({f.mime_type})")
    while True:
        try:
            raw = input(
                f"\nEnter index (1–{len(info.formats)}) or format id: ",
            )
        except EOFError:
            print()
            raise SystemExit(2) from None
        resolved = _resolve_format_choice(info, raw)
        if resolved is not None:
            return resolved
        _err("Invalid choice. Use a row number or a valid format id.")


def cmd_download(
    url: str,
    output_dir: str,
    format_id: str | None,
    non_interactive: bool,
) -> int:
    try:
        info = YtDlpService.fetch_formats(url)
    except (InvalidUrlError, UnsupportedPlatformError) as e:
        _err(str(e))
        return 2
    except VideoNotFoundError:
        _err("Video not found.")
        return 1
    except FormatNotAvailableError as e:
        _err(str(e))
        return 1
    except YtdlpFailedError as e:
        _err(str(e))
        return 1

    if format_id:
        fmt = format_id.strip()
        if not FORMAT_ID_PATTERN.match(fmt):
            _err("Invalid format id (disallowed characters).")
            return 2
    elif non_interactive:
        _err("Non-interactive mode requires -f/--format.")
        return 2
    else:
        if not sys.stdin.isatty():
            _err("No TTY; pass -f/--format or use -y with -f for scripts.")
            return 2
        fmt = _interactive_format(info)

    try:
        path = YtDlpService.download_to_directory(
            url,
            fmt,
            output_dir,
            video_info=info,
        )
    except (InvalidUrlError, YtdlpFailedError) as e:
        _err(str(e))
        return 1

    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video-dl",
        description="List formats or download a video using the same yt-dlp settings "
        "as the API (see backend .env).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("formats", help="List available formats for a URL")
    pf.add_argument("url", help="Video page URL")
    pf.add_argument(
        "--json",
        action="store_true",
        help="Print full metadata as JSON",
    )

    pd = sub.add_parser("download", help="Download using a format id")
    pd.add_argument("url", help="Video page URL")
    pd.add_argument(
        "-f",
        "--format",
        dest="format_id",
        default=None,
        help="Format id (from formats list), e.g. 18, 22, or a merged selector",
    )
    pd.add_argument(
        "-o",
        "--output-dir",
        default="~/Downloads",
        help="Directory for the saved file (default: ~/Downloads)",
    )
    pd.add_argument(
        "-y",
        "--non-interactive",
        action="store_true",
        help="Do not prompt; requires -f/--format",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "formats":
        return cmd_formats(args.url, args.json)

    if args.command == "download":
        out = args.output_dir
        return cmd_download(
            args.url,
            out,
            args.format_id,
            args.non_interactive,
        )

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
