from __future__ import annotations

import re

from app.schemas import ChunkPayload, ChunkingConfig, Domain


class MarkdownChunker:
    """按 Markdown 二级标题切 TMS 异常码手册。

    TMS 的最小知识单元是“异常码 -> 现象 -> 排查 -> 建议 -> 风险”。
    因此不能用固定长度把一个异常码切碎，而是优先按 `## E1001` 这类标题切。
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig(chunk_size=1200, overlap=80)

    def chunk(
        self,
        markdown: str,
        *,
        source: str,
        domain: Domain = "tms",
    ) -> list[ChunkPayload]:
        sections = _split_markdown_sections(markdown)
        chunks: list[ChunkPayload] = []
        for title, body in sections:
            text = f"{title}\n{body}".strip()
            metadata = _metadata_from_section(text)
            chunk_id = str(metadata.get("chunk_id") or _slug(title))
            chunks.append(
                ChunkPayload(
                    chunk_id=chunk_id,
                    domain=domain,
                    source=source,
                    title=title.lstrip("# ").strip(),
                    text=text,
                    metadata=metadata,
                )
            )
        return chunks


class QAChunker:
    """按 Q/A 对切 OTT FAQ。

    OTT FAQ 的自然检索单元就是一问一答；用户问的问题通常和 Q 字段高度相似。
    """

    def chunk(
        self,
        markdown: str,
        *,
        source: str,
        domain: Domain = "ott",
    ) -> list[ChunkPayload]:
        chunks: list[ChunkPayload] = []
        blocks = re.split(r"\n(?=##\s+)", markdown.strip())
        for block in blocks:
            if not block.strip().startswith("##"):
                continue
            lines = block.strip().splitlines()
            title = lines[0].lstrip("# ").strip()
            metadata = _metadata_from_section(block)
            chunk_id = str(metadata.get("chunk_id") or _slug(title))
            chunks.append(
                ChunkPayload(
                    chunk_id=chunk_id,
                    domain=domain,
                    source=source,
                    title=title,
                    text=block.strip(),
                    metadata=metadata,
                )
            )
        return chunks


class FixedChunker:
    """固定长度切片器，给结构较弱的养老指南兜底。

    它不是简单按字符硬切，而是优先回退到中文句号、分号、换行等边界。
    这样可以尽量避免切断血压数值、药品剂量和“立即就医”类禁忌句。
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig(chunk_size=700, overlap=80)

    def chunk(
        self,
        markdown: str,
        *,
        source: str,
        domain: Domain = "elderly",
        chunk_prefix: str = "elderly",
    ) -> list[ChunkPayload]:
        sections = _split_markdown_sections(markdown)
        if sections:
            chunks: list[ChunkPayload] = []
            for section_index, (title, body) in enumerate(sections, start=1):
                text = f"{title}\n{body}".strip()
                metadata = _metadata_from_section(text)
                base_id = str(metadata.get("chunk_id") or f"{chunk_prefix}_{section_index:03d}")
                chunks.extend(
                    self._chunk_text(
                        text,
                        source=source,
                        domain=domain,
                        base_id=base_id,
                        base_title=title.lstrip("# ").strip(),
                        base_metadata=metadata,
                    )
                )
            return chunks

        text = _strip_top_heading(markdown)
        return self._chunk_text(
            text,
            source=source,
            domain=domain,
            base_id=chunk_prefix,
            base_title="养老健康指南",
            base_metadata={"strategy": "fixed_with_sentence_boundary"},
        )

    def _chunk_text(
        self,
        text: str,
        *,
        source: str,
        domain: Domain,
        base_id: str,
        base_title: str,
        base_metadata: dict[str, object],
    ) -> list[ChunkPayload]:
        chunks: list[ChunkPayload] = []
        start = 0
        index = 1
        while start < len(text):
            hard_end = min(start + self.config.chunk_size, len(text))
            end = _best_sentence_boundary(text, start, hard_end)
            if end <= start:
                end = hard_end
            part = text[start:end].strip()
            if part:
                chunk_id = base_id if index == 1 else f"{base_id}_{index:02d}"
                metadata = dict(base_metadata)
                metadata.update(
                    {
                        "chunk_id": chunk_id,
                        "section_index": index,
                        "strategy": "fixed_with_sentence_boundary",
                    }
                )
                chunks.append(
                    ChunkPayload(
                        chunk_id=chunk_id,
                        domain=domain,
                        source=source,
                        title=base_title,
                        text=part,
                        metadata=metadata,
                    )
                )
                index += 1
            if end >= len(text):
                break
            start = max(end - self.config.overlap, 0)
        return chunks


def _split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
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


def _metadata_from_section(text: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for line in text.splitlines():
        if "：" not in line:
            continue
        key, value = line.split("：", 1)
        key = key.strip("- * ")
        value = value.strip()
        if not key or not value:
            continue
        normalized_key = {
            "ChunkID": "chunk_id",
            "异常码": "error_code",
            "FAQID": "faq_id",
            "风险等级": "risk_level",
            "CDN厂商": "cdn_vendor",
            "播放器版本": "player_version",
            "主题": "topic",
        }.get(key, key)
        metadata[normalized_key] = value
    if "chunk_id" not in metadata:
        first_line = text.splitlines()[0] if text.splitlines() else "chunk"
        metadata["chunk_id"] = _slug(first_line)
    metadata["strategy"] = metadata.get("strategy", "section")
    return metadata


def _slug(text: str) -> str:
    ascii_text = re.sub(r"[^a-zA-Z0-9_]+", "_", text.lower()).strip("_")
    if ascii_text:
        return ascii_text
    digest = str(abs(hash(text)))
    return f"chunk_{digest}"


def _strip_top_heading(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _best_sentence_boundary(text: str, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return len(text)
    window = text[start:hard_end]
    for marker in ("\n## ", "\n### ", "。", "；", "\n"):
        index = window.rfind(marker)
        if index > max(20, len(window) // 2):
            return start + index + len(marker)
    return hard_end
