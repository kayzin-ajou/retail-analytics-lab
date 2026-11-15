"""Download the original UCI archive to the local machine (not committed)."""
from pathlib import Path
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from zipfile import ZipFile

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "online_retail_original.zip"
MAX_SIZE = 75 * 1024 * 1024


def download(force: bool = False) -> Path:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and not force:
        return TARGET
    tmp = TARGET.with_suffix(".download")
    req = urllib.request.Request(URL, headers={"User-Agent": "RetailAnalyticsLab/1.0 (educational; data from UCI)"})
    hasher = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=65) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_SIZE:
                    raise ValueError("다운로드 파일이 예상 크기를 초과했습니다.")
                f.write(chunk)
                hasher.update(chunk)
        with ZipFile(tmp) as z:
            names = z.namelist()
            if not any(x.lower().endswith(".xlsx") for x in names):
                raise ValueError("ZIP 내부에서 XLSX를 찾지 못했습니다.")
            bad = z.testzip()
            if bad:
                raise ValueError("ZIP 무결성 검사 실패: " + bad)
        os.replace(tmp, TARGET)
        meta = {"source": URL, "dataset": "UCI Online Retail (#352)",
                "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                "bytes": size, "sha256": hasher.hexdigest(),
                "license": "CC BY 4.0", "doi": "10.24432/C5BW33"}
        (ROOT / "data" / "provenance.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return TARGET
    finally:
        if tmp.exists():
            tmp.unlink()


if __name__ == "__main__":
    print("UCI 원본 데이터를 다운로드합니다. 약 22.6MB이며 인터넷이 필요합니다.")
    try:
        result = download()
        print("완료:", result)
    except Exception as exc:
        raise SystemExit(f"다운로드 실패: {exc}\n공식 자료 페이지: https://archive.ics.uci.edu/dataset/352/online+retail")
