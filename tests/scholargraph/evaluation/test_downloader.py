from __future__ import annotations

from pathlib import Path

from scripts.prepare_scholargraph_eval import download_dataset


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"%PDF-1.7\nmock"


def test_downloader_uses_manifest_filenames_and_skips_existing(
    tmp_path: Path, monkeypatch
) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse()

    monkeypatch.setattr(
        "scripts.prepare_scholargraph_eval.urlopen",
        fake_urlopen,
    )

    first = download_dataset(tmp_path)
    second = download_dataset(tmp_path)

    assert len(first) == 6
    assert first == second
    assert len(calls) == 6
    assert all(path.read_bytes().startswith(b"%PDF-") for path in first)
