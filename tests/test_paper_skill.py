from app.skills.registry import SkillRegistry, is_paper_request
from app.tools.paper_search import normalize_semantic_scholar_paper


def test_paper_skill_intent_detection() -> None:
    assert is_paper_request("推荐三篇 CMR flow matching 论文")
    assert is_paper_request("这篇 paper 的 ablation 怎么做的？")
    assert not is_paper_request("帮我计算 12 * 8")


def test_skill_file_can_be_loaded() -> None:
    instructions = SkillRegistry("skills").instructions_for("解读这篇论文的实验指标")
    assert "read_paper_evidence" in instructions
    assert "实验分析" in instructions


def test_semantic_scholar_normalization() -> None:
    item = {
        "paperId": "abc",
        "title": "Example Paper",
        "authors": [{"name": "A"}, {"name": "B"}],
        "year": 2026,
        "venue": "MICCAI",
        "abstract": "abstract",
        "citationCount": 12,
        "influentialCitationCount": 3,
        "externalIds": {"DOI": "10.1/example", "ArXiv": "2601.00001"},
        "openAccessPdf": {"url": "https://example.org/paper.pdf"},
        "url": "https://www.semanticscholar.org/paper/abc",
    }
    normalized = normalize_semantic_scholar_paper(item)
    assert normalized["doi"] == "10.1/example"
    assert normalized["arxiv_id"] == "2601.00001"
    assert normalized["authors"] == ["A", "B"]
