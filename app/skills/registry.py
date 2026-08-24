from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


TaskRoute = Literal["lab_resource", "paper_reading", "general"]

_STRONG_PAPER_MARKERS = (
    "论文",
    "文献",
    "paper",
    "arxiv",
    "doi",
    "期刊",
    "journal",
    "消融",
    "ablation",
    "baseline",
)


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

_LAB_MARKERS = (
    "实验室",
    "gpu",
    "算力",
    "服务器",
    "集群",
    "资源申请",
    "资源",
    "账号",
    "登录",
    "审批",
    "导师",
    "dbcloud",
    "数据合规",
    "脱敏",
    "制度",
    "流程",
)


@dataclass(frozen=True, slots=True)
class SkillMatch:
    route: TaskRoute
    skill_name: str | None
    instructions: str


def classify_task_route(message: str) -> TaskRoute:
    """Deterministically route a request before the LLM/tool graph runs."""

    lowered = message.lower()

    # Explicit academic-paper language wins even when words such as
    # "数据集" or "资源" are also present.
    if any(marker in lowered for marker in _STRONG_PAPER_MARKERS):
        return "paper_reading"

    paper_score = sum(marker in lowered for marker in _PAPER_MARKERS)
    lab_score = sum(marker in lowered for marker in _LAB_MARKERS)

    # An explicit lab context should keep queries such as
    # "实验室的数据集放在哪里" out of the paper route.
    if lab_score and lab_score >= paper_score:
        return "lab_resource"
    if paper_score:
        return "paper_reading"
    if lab_score:
        return "lab_resource"
    return "general"


def is_paper_request(message: str) -> bool:
    return classify_task_route(message) == "paper_reading"


def is_lab_resource_request(message: str) -> bool:
    return classify_task_route(message) == "lab_resource"


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

    def match(self, message: str) -> SkillMatch:
        route = classify_task_route(message)
        if route == "paper_reading":
            skill_name = "paper-reader"
        elif route == "lab_resource":
            skill_name = "lab-resource"
        else:
            skill_name = None

        return SkillMatch(
            route=route,
            skill_name=skill_name,
            instructions=self._load(skill_name) if skill_name else "",
        )

    def instructions_for(self, message: str) -> str:
        return self.match(message).instructions
