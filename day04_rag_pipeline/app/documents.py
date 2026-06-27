from __future__ import annotations

from pathlib import Path

from app.chunker import FixedChunker, MarkdownChunker, QAChunker
from app.schemas import ChunkPayload


CORPUS_DIR = Path(__file__).resolve().parents[1] / "data" / "corpus"


def load_corpus_chunks(corpus_dir: Path | None = None) -> list[ChunkPayload]:
    """读取三份 Day 4 语料并切成 ChunkPayload。

    这里集中维护文件名和切片策略，避免测试、评估脚本、真实入库各写一套路径。
    """

    root = corpus_dir or CORPUS_DIR
    tms_text = (root / "tms_ops_manual.md").read_text(encoding="utf-8")
    ott_text = (root / "ott_ops_faq.md").read_text(encoding="utf-8")
    elderly_text = (root / "elderly_health_guide.md").read_text(encoding="utf-8")

    chunks: list[ChunkPayload] = []
    chunks.extend(
        MarkdownChunker().chunk(
            tms_text,
            source="tms_ops_manual.md",
            domain="tms",
        )
    )
    chunks.extend(
        QAChunker().chunk(
            ott_text,
            source="ott_ops_faq.md",
            domain="ott",
        )
    )
    chunks.extend(
        FixedChunker().chunk(
            elderly_text,
            source="elderly_health_guide.md",
            domain="elderly",
            chunk_prefix="elderly",
        )
    )
    return chunks

