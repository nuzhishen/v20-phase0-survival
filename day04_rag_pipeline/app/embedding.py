from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import math
import subprocess
from pathlib import Path


_KEY_TERMS = [
    # TMS 运维语料高权重词。中文 query 很短，强业务词必须压过普通汉字重叠。
    "设备离线",
    "离线",
    "72",
    "ota",
    "下载",
    "超时",
    "固件",
    "版本",
    "不一致",
    "批量",
    "失败",
    "脚本",
    "emqx",
    "证书",
    "存储",
    "空间",
    "回滚",
    "cdn",
    "带宽",
    "时钟",
    "ntp",
    # OTT 语料高权重词。
    "直播",
    "卡顿",
    "播放器",
    "首帧",
    "drm",
    "license",
    "卡死",
    "灰屏",
    "epg",
    "节目单",
    "字幕",
    "音画",
    "同步",
    "码率",
    "清晰度",
    "黑屏",
    "403",
    "token",
    "鉴权",
    "回看",
    # 老年健康语料高权重词。
    "高血压",
    "血压",
    "血糖",
    "低血糖",
    "跌倒",
    "胸痛",
    "服药",
    "睡眠",
    "运动",
    "饮食",
    "脱水",
    "发热",
    "认知",
    "走失",
    "疼痛",
    "便秘",
    "水肿",
    "体重",
    "呼吸困难",
    "呼吸",
]


class EmbeddingProvider(ABC):
    """Embedding 抽象层。

    Day 4 测试默认使用 `MockEmbedding`，保证不依赖网络、GPU 或模型下载。
    真实 BGE 通过 `BGEEmbedding` 接入，它会调用 WSL 里的 Python 环境。
    """

    @property
    @abstractmethod
    def vector_size(self) -> int:
        """返回向量维度，必须和 Qdrant Collection 的 vector size 一致。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文本。"""

    def embed_query(self, query: str) -> list[float]:
        """查询向量化只是批量接口的单条包装。"""

        return self.embed_texts([query])[0]


class MockEmbedding(EmbeddingProvider):
    """确定性本地 Embedding。

    设计目标不是模拟真实语义模型，而是保证工程链路稳定可测：
    - 同一段文本永远得到同一向量。
    - 相同关键词/字符越多，余弦相似度通常越高。
    - 不依赖外部模型，pytest 可以在任何机器上跑。

    实现方式是“字符 n-gram 哈希桶”：
    1. 把文本切成中文双字/三字短语、ASCII token 和业务关键词。
    2. 每个 token 通过 blake2b hash 映射到固定维度。
    3. 使用 L2 归一化，让 Qdrant COSINE 与内存向量库行为一致。
    """

    def __init__(self, vector_size: int = 256) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive")
        self._vector_size = vector_size

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._vector_size
        for token in _tokens_for_hashing(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._vector_size
            # 这里故意使用非负词频，而不是随机正负号的 SimHash。
            # Day 4 的 query 往往很短，例如“设备离线超过72小时”；如果短文本
            # 刚好被负号抵消，应该命中的 chunk 会被阈值挡掉。非负桶更接近
            # “关键词越重叠越相似”的教学目标，也更适合作为稳定测试基线。
            vector[bucket] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class ZeroEmbedding(EmbeddingProvider):
    """故障注入用 Embedding。

    返回全 0 向量，专门用于测试 Retriever 是否能把低质量检索标记为
    `low_confidence`，而不是强行给出看似相关的结果。
    """

    def __init__(self, vector_size: int = 256) -> None:
        self._vector_size = vector_size

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._vector_size for _ in texts]


class BGEEmbedding(EmbeddingProvider):
    """通过 WSL 调用 BGE 中文 embedding 模型。

    当前 Windows 项目虚拟环境是 Python 3.14，不适合直接安装 PyTorch。
    因此真实 BGE 运行在 WSL 的 Python 3.10 环境：
    `/home/aaron/venvs/v20-day4-bge/bin/python`

    这个包装器把待编码文本写到子进程 stdin，子进程用 sentence-transformers
    输出 JSON 向量。它比进程内调用慢，但足够用于 Day 4 smoke test 和真实入库。
    """

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        vector_size: int = 512,
        python_executable: str = "/home/aaron/venvs/v20-day4-bge/bin/python",
        use_wsl: bool = True,
    ) -> None:
        self.model_name = model_name
        self._vector_size = vector_size
        self.python_executable = python_executable
        self.use_wsl = use_wsl

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        script = """
import json
import sys
from sentence_transformers import SentenceTransformer

payload = json.load(sys.stdin)
model = SentenceTransformer(payload["model_name"], device="cpu")
vectors = model.encode(payload["texts"], normalize_embeddings=True)
print(json.dumps(vectors.tolist(), ensure_ascii=False))
"""
        command = [self.python_executable, "-c", script]
        if self.use_wsl:
            command = ["wsl", "-e", *command]

        # 这里不用 `text=True`，因为 Windows PowerShell 默认代码页可能不是 UTF-8。
        # 如果把中文 JSON 按本地代码页传给 WSL，tokenizer 会收到异常字符。
        # 显式使用 UTF-8 bytes，可以保证中文 query 原样进入 BGE。
        payload_bytes = json.dumps(
            {"model_name": self.model_name, "texts": texts},
            ensure_ascii=False,
        ).encode("utf-8")
        completed = subprocess.run(
            command,
            input=payload_bytes,
            capture_output=True,
            check=False,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        if completed.returncode != 0:
            raise RuntimeError(
                "BGE embedding failed: "
                f"stdout={stdout!r}, stderr={stderr!r}"
            )

        vectors = json.loads(stdout)
        for vector in vectors:
            if len(vector) != self._vector_size:
                raise ValueError(
                    f"BGE vector size mismatch: expected {self._vector_size}, got {len(vector)}"
                )
        return vectors

    def is_available(self) -> bool:
        """轻量检查 WSL BGE Python 是否存在。"""

        if not self.use_wsl:
            return Path(self.python_executable).exists()
        completed = subprocess.run(
            ["wsl", "-e", "test", "-x", self.python_executable],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0


def _tokens_for_hashing(text: str) -> list[str]:
    """把中文/英文混合文本拆成简单 token。

    这里不引入 jieba 等分词依赖，避免 Day 4 变成中文分词实验。
    这里故意不使用中文单字。单字会让“天气、机票、股票”这类无关 query
    仅凭常用字撞上业务语料；双字/三字短语更能保留中文语义边界。
    ASCII token 则保留 E1001、CDN、EMQX 等运维术语和编号。
    """

    normalized = text.lower()
    chars = [char for char in normalized if not char.isspace()]
    tokens: list[str] = []
    tokens.extend("".join(chars[index : index + 2]) for index in range(len(chars) - 1))
    tokens.extend("".join(chars[index : index + 3]) for index in range(len(chars) - 2))

    for term in _KEY_TERMS:
        if term in normalized:
            # term: 前缀避免和普通 n-gram 共用同一语义空间。
            # 重复 12 次相当于给业务词加权，能明显降低“天气、机票、股票”
            # 这类无关 query 只靠常用汉字撞上业务语料的概率。
            tokens.extend([f"term:{term}"] * 12)

    current_ascii: list[str] = []
    for char in normalized:
        if char.isascii() and (char.isalnum() or char in {"_", "-"}):
            current_ascii.append(char)
        else:
            if current_ascii:
                tokens.append("".join(current_ascii))
                current_ascii.clear()
    if current_ascii:
        tokens.append("".join(current_ascii))

    return [token for token in tokens if token]
