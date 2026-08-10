"""Download the public PDFs declared by the ScholarGraph evaluation manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import Request, urlopen

from scholargraph.evaluation import DEFAULT_DATASET_PATH, load_evaluation_dataset


def download_dataset(
    output_dir: str | Path,
    *,
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    force: bool = False,
) -> list[Path]:
    dataset = load_evaluation_dataset(dataset_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for paper in dataset.papers:
        destination = output / paper.filename
        if destination.exists() and not force:
            downloaded.append(destination)
            continue
        request = Request(
            paper.pdf_url,
            headers={"User-Agent": "ScholarGraph evaluation dataset downloader/1.0"},
        )
        with urlopen(request, timeout=60) as response:
            payload = response.read()
        if not payload.startswith(b"%PDF-"):
            raise RuntimeError(f"download for {paper.paper_id} is not a PDF")
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        downloaded.append(destination)
    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="inputs/scholargraph-eval")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    paths = download_dataset(args.output, dataset_path=args.dataset, force=args.force)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
