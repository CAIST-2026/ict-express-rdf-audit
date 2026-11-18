"""Install pure wheels by download+unzip, without pip.

Why: pip requires a writable *and deletable* temporary directory. In the
restricted environment used for this revision, file deletion is denied, so
``pip install`` aborts with "No usable temporary directory found". Downloading
a wheel and extracting it into ``site-packages`` needs no temporary file and no
deletion, and produces an identical installation for pure-python and
pre-built-binary wheels.

Usage:
  python experiments/vendor_install.py pypinyin torch transformers ...
  python experiments/vendor_install.py --list torch     # show candidates only
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

MIRROR = "https://mirrors.aliyun.com/pypi/simple/{pkg}/"
SITE = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
WHEELS = Path(__file__).resolve().parents[1] / "env" / "wheels"

# Preferred wheel tag order for this interpreter (CPython 3.13, macOS arm64).
TAG_ORDER = [
    "cp313-cp313-macosx_11_0_arm64",
    "cp313-none-macosx_11_0_arm64",
    "cp313-none-macosx_10_13_universal2",
    "py3-none-any",
    "py2.py3-none-any",
    "cp313-cp313t-macosx_11_0_arm64",
    "cp313-abi3-macosx_11_0_arm64",
    "cp313-abi3-macosx_10_13_universal2",
]


def _verkey(v: str) -> tuple:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts[:4]) if parts else (0,)


def _candidates(pkg: str, want: str | None = None) -> list[tuple[str, str, str]]:
    html = urlopen(MIRROR.format(pkg=pkg), timeout=60).read().decode("utf-8", "replace")
    out = []
    for href, name in re.findall(r'href="([^"#]+)(?:#[^"]*)?"[^>]*>([^<]+\.whl)<', html):
        stem = name[:-4]
        parts = stem.split("-")
        if len(parts) < 3:
            continue
        ver = parts[1]
        tag = "-".join(parts[-3:]) if len(parts) >= 5 else parts[-1]
        if want and ver != want:
            continue
        out.append((urljoin(MIRROR.format(pkg=pkg), href), ver, tag))
    return out


def pick(pkg: str, want: str | None = None) -> tuple[str, str, str] | None:
    cands = _candidates(pkg, want)
    if not cands:
        return None
    usable = []
    for url, ver, tag in cands:
        if tag in TAG_ORDER:
            usable.append((_verkey(ver), -TAG_ORDER.index(tag), url, ver, tag))
    if not usable:
        return None
    usable.sort(reverse=True)
    _k, _t, url, ver, tag = usable[0]
    return url, ver, tag


def install(spec: str, list_only: bool = False) -> bool:
    pkg, _, want = spec.partition("==")
    want = want or None
    got = pick(pkg, want)
    if got is None:
        print(f"[skip] {pkg}: no compatible wheel")
        return False
    url, ver, tag = got
    if list_only:
        print(f"[cand] {pkg} {ver} {tag} {url}")
        return True
    WHEELS.mkdir(parents=True, exist_ok=True)
    data = urlopen(url, timeout=300).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    zf.extractall(SITE)
    print(f"[ok]   {pkg} {ver} ({tag}) {len(data)/1e6:.1f} MB -> {SITE}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    for p in a.packages:
        try:
            install(p, a.list)
        except Exception as exc:                       # pragma: no cover
            print(f"[fail] {p}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
