from __future__ import annotations

from pathlib import Path


_PAPER_MARKERS = (
    "论文",
    "文献",
    "paper",
    "arxiv",
    "doi",
    "预印本",
    "期刊",
    "journal",
    "conference",
    "消融",
    "ablation",
    "baseline",
    "创新点",
    "实验指标",
    "数据集",
)


def is_paper_request(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _PAPER_MARKERS)


class SkillRegistry:
    """Load trusted local SKILL.md instructions and activate them by intent."""

    def __init__(self, skills_dir: str = "skills") -> None:
        root = Path(skills_dir)
        if not root.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            root = repo_root / root
        self.root = root
        self._cache: dict[str, str] = {}

    def _load(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]
        path = self.root / name / "SKILL.md"
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8").strip()
        self._cache[name] = content
        return content

    def instructions_for(self, message: str) -> str:
        if is_paper_request(message):
            return self._load("paper-reader")
        return ""
