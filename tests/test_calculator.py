import pytest

from app.agent import UnsafeExpressionError, extract_arithmetic_expression, safe_calculate


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 * 3", 7.0),
        ("(12 + 8) * 3", 60.0),
        ("2 ** 8", 256.0),
        ("7 // 2", 3.0),
    ],
)
def test_safe_calculate(expression: str, expected: float) -> None:
    assert safe_calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "open('/etc/passwd').read()",
        "(1).__class__",
        "[1, 2, 3][0]",
        "2 ** 100",
    ],
)
def test_safe_calculate_rejects_code_execution(expression: str) -> None:
    with pytest.raises((UnsafeExpressionError, SyntaxError)):
        safe_calculate(expression)


def test_extract_arithmetic_expression_from_natural_language() -> None:
    assert extract_arithmetic_expression("请计算 (12 + 8) * 3") == "(12 + 8) * 3"
