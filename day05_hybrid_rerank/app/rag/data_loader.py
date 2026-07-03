from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from app.rag.types import Chunk, Domain, EvalQuery


DAY05_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = DAY05_DIR.parent
DAY04_DIR = REPO_ROOT / "day04_rag_pipeline"
CORPUS_DIR = DAY04_DIR / "data" / "corpus"
EVAL_PATH = DAY04_DIR / "data" / "eval" / "rag_eval_queries.jsonl"


def load_corpus_chunks(corpus_dir: Path | None = None) -> list[Chunk]:
    root = corpus_dir or CORPUS_DIR
    files: tuple[tuple[str, Domain], ...] = (
        ("tms_ops_manual.md", "tms"),
        ("ott_ops_faq.md", "ott"),
        ("elderly_health_guide.md", "elderly"),
    )

    chunks: list[Chunk] = []
    for filename, domain in files:
        text = (root / filename).read_text(encoding="utf-8")
        for title, body in _split_sections(text):
            block = f"{title}\n{body}".strip()
            metadata = _metadata_from_section(block)
            chunk_id = metadata.get("chunk_id") or _slug(title)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    domain=domain,
                    source=filename,
                    title=title.lstrip("# ").strip(),
                    text=block,
                    metadata=metadata,
                )
            )
    return chunks


def load_eval_queries(path: Path | None = None) -> list[EvalQuery]:
    eval_path = path or EVAL_PATH
    queries: list[EvalQuery] = []
    for line_number, line in enumerate(eval_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        try:
            queries.append(
                EvalQuery(
                    query_id=str(raw["query_id"]),
                    query=str(raw["query"]),
                    domain=raw["domain"],
                    expected_chunk_id=str(raw["expected_chunk_id"]),
                    expected_keywords=tuple(str(item) for item in raw["expected_keywords"]),
                    ground_truth_context=str(raw["ground_truth_context"]),
                    ground_truth_answer=str(raw["ground_truth_answer"]),
                )
            )
        except KeyError as error:
            raise ValueError(f"Invalid eval query at line {line_number}: missing {error}") from error
    return queries


def index_text_for_chunk(chunk: Chunk) -> str:
    metadata_text = " ".join(str(value) for value in chunk.metadata.values())
    return f"{chunk.title}\n{metadata_text}\n{chunk.text}"


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    lines = markdown.strip().splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, current_body))
            current_title = line
            current_body = []
        elif current_title is not None:
            current_body.append(line)

    if current_title is not None:
        sections.append((current_title, current_body))

    return [(title, "\n".join(body).strip()) for title, body in sections]


def _metadata_from_section(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    key_map = {
        "ChunkID": "chunk_id",
        "异常码": "error_code",
        "FAQID": "faq_id",
        "风险等级": "risk_level",
        "CDN厂商": "cdn_vendor",
        "播放器版本": "player_version",
        "主题": "topic",
    }
    for line in text.splitlines():
        if "：" not in line:
            continue
        key, value = line.split("：", 1)
        normalized_key = key_map.get(key.strip("- * "), key.strip("- * "))
        stripped = value.strip()
        if normalized_key and stripped:
            metadata[normalized_key] = stripped
    if "chunk_id" not in metadata:
        metadata["chunk_id"] = _slug(text.splitlines()[0] if text.splitlines() else "chunk")
    return metadata


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", text.lower()).strip("_")
    return slug or f"chunk_{abs(hash(text))}"
