from decimal import Decimal
import pytest
from app.engine.formulas import evaluate_formula, topological_order
from app.engine.rules import evaluate_condition

@pytest.mark.parametrize("op,expected", [("eq",True),("ne",False),("gt",False),("gte",True),("lt",False),("lte",True),("in",True),("contains",True)])
def test_rule_operations(op, expected):
    args = ["$x", [1,2]] if op == "in" else [[1,2], "$x"] if op == "contains" else ["$x",1]
    assert evaluate_condition({"op":op,"args":args},{"x":1}).value is expected

def test_nested_rule_has_trace():
    result = evaluate_condition({"op":"and","args":[{"op":"eq","args":["$x",1]},{"op":"not","args":[{"op":"eq","args":["$x",2]}]}]},{"x":1})
    assert result.value and len(result.trace) >= 3

def test_money_formula_decimal_and_trace():
    value, trace = evaluate_formula({"op":"round","args":[{"op":"div","args":["$amount",3]},2]},{"amount":10})
    assert value == Decimal("3.33") and trace

def test_formula_rejects_zero_division_and_unknown_operation():
    with pytest.raises(ValueError,match="zero"): evaluate_formula({"op":"div","args":[1,0]}, {})
    with pytest.raises(ValueError,match="unknown"): evaluate_formula({"op":"exec","args":[]}, {})

def test_cycle_is_rejected():
    with pytest.raises(ValueError,match="cycle"): topological_order({"a":{"b"},"b":{"a"}})
