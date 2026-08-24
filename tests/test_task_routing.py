from app.skills.registry import SkillRegistry, classify_task_route


def test_routes_explicit_paper_request_to_paper_reader() -> None:
    assert (
        classify_task_route("请解读这篇论文的创新点、baseline 和消融实验")
        == "paper_reading"
    )


def test_routes_paper_followup_with_dataset_to_paper_reader() -> None:
    assert classify_task_route("它用了哪些数据集？") == "paper_reading"


def test_routes_gpu_request_to_lab_resource() -> None:
    assert classify_task_route("GPU 资源申请需要哪些材料？") == "lab_resource"


def test_explicit_lab_context_wins_for_lab_dataset_question() -> None:
    assert classify_task_route("实验室的数据集放在哪台服务器？") == "lab_resource"


def test_skill_registry_exposes_selected_skill() -> None:
    registry = SkillRegistry("skills")

    lab = registry.match("DBCloud 怎么登录？")
    paper = registry.match("请阅读这篇 arXiv 论文")

    assert lab.route == "lab_resource"
    assert lab.skill_name == "lab-resource"
    assert "search_knowledge" in lab.instructions

    assert paper.route == "paper_reading"
    assert paper.skill_name == "paper-reader"
    assert paper.instructions
