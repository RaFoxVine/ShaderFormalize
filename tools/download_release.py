"""Bounded, resumable release downloads using validated HTTP byte ranges."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_part(url, start, end, size, cache, deadline, stopped):
    part = cache / f"{start:012d}-{end:012d}.part"
    length = end - start + 1
    if part.exists() and part.stat().st_size > length:
        raise RuntimeError(f"Oversized cached range: {part}")
    for attempt in range(4):
        done = part.stat().st_size if part.exists() else 0
        if done == length:
            return part
        if stopped.is_set() or time.monotonic() >= deadline:
            raise RuntimeError("Download deadline reached; valid partial ranges retained")
        actual_start = start + done
        temporary = part.with_suffix(".transfer")
        header = part.with_suffix(".headers")
        seconds = max(1, min(600, int(deadline - time.monotonic())))
        result = subprocess.run([
            "curl.exe", "-4", "--location", "--fail", "--silent", "--show-error",
            "--connect-timeout", "15", "--max-time", str(seconds),
            "--range", f"{actual_start}-{end}", "--dump-header", str(header),
            "--output", str(temporary), url,
        ], capture_output=True, text=True, encoding="utf-8", errors="replace")
        headers = header.read_text(encoding="latin-1") if header.exists() else ""
        matches = re.findall(r"(?im)^content-range:\s*bytes (\d+)-(\d+)/(\d+)\s*$", headers)
        if not matches:
            if re.search(r"(?im)^HTTP/\S+ 200\b", headers):
                stopped.set()
                raise RuntimeError("Server ignored Range; refusing full-file fragments")
            if attempt == 3:
                raise RuntimeError(f"Range {actual_start}-{end} failed: {result.stderr.strip()}")
            continue
        returned = tuple(int(value) for value in matches[-1])
        if returned != (actual_start, end, size):
            stopped.set()
            raise RuntimeError(f"Unexpected Content-Range: {returned}")
        received = temporary.stat().st_size if temporary.exists() else 0
        if received > end - actual_start + 1:
            stopped.set()
            raise RuntimeError("Server sent too many bytes")
        # A timed-out transfer still contains a validated prefix of this range.
        if received:
            with part.open("ab") as destination, temporary.open("rb") as source:
                shutil.copyfileobj(source, destination)
            temporary.unlink()
        if part.exists() and part.stat().st_size == length:
            return part
        if attempt == 3:
            raise RuntimeError(f"Incomplete range retained: {part.name}")
    raise RuntimeError("Unreachable download state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk-mib", type=int, default=4)
    parser.add_argument("--max-seconds", type=int, default=1800)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16 or not 1 <= args.chunk_mib <= 64:
        parser.error("workers must be1..16 and chunk-mib1..64")
    if args.size <= 0 or args.max_seconds <= 0 or not re.fullmatch("[0-9a-f]{64}", args.sha256):
        parser.error("positive size/deadline and lowercase SHA256 required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.stat().st_size == args.size and sha256(args.output) == args.sha256:
        print("Verified existing archive", flush=True)
        return
    cache = args.output.parent / f"{args.output.name}.parts"
    cache.mkdir(exist_ok=True)
    chunk_size = args.chunk_mib * 1024 * 1024
    ranges = [(start, min(start + chunk_size, args.size) - 1)
              for start in range(0, args.size, chunk_size)]
    started = time.monotonic()
    deadline = started + args.max_seconds
    stopped = threading.Event()
    complete = 0
    print(f"Downloading {args.size} bytes in {len(ranges)} ranges, {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download_part, args.url, start, end, args.size, cache, deadline, stopped)
                   for start, end in ranges]
        try:
            for future in as_completed(futures):
                future.result()
                complete += 1
                print(f"Ranges complete: {complete}/{len(ranges)}; elapsed {time.monotonic()-started:.1f}s", flush=True)
        except Exception:
            stopped.set()
            for future in futures:
                future.cancel()
            raise
    assembled = args.output.with_suffix(args.output.suffix + ".assembled")
    with assembled.open("wb") as destination:
        for start, end in ranges:
            with (cache / f"{start:012d}-{end:012d}.part").open("rb") as source:
                shutil.copyfileobj(source, destination)
    if assembled.stat().st_size != args.size or sha256(assembled) != args.sha256:
        raise RuntimeError("Complete archive failed size/SHA256 verification")
    assembled.replace(args.output)
    print(f"Verified archive SHA256 {args.sha256}", flush=True)


if __name__ == "__main__":
    main()
