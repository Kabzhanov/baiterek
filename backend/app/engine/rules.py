from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class RuleResult:
    value: bool
    trace: tuple[str, ...]

def evaluate_condition(expr: dict, data: dict[str, Any]) -> RuleResult:
    op, args = expr.get("op"), expr.get("args", [])
    def value(item):
        return data.get(item[1:]) if isinstance(item, str) and item.startswith("$") else item
    if op in {"and", "or"}:
        children = [evaluate_condition(item, data) for item in args]
        result = all(c.value for c in children) if op == "and" else any(c.value for c in children)
        return RuleResult(result, (f"{op}={result}",) + tuple(t for c in children for t in c.trace))
    if op == "not":
        child = evaluate_condition(args[0], data)
        return RuleResult(not child.value, (f"not={not child.value}",) + child.trace)
    if op not in {"eq","ne","gt","gte","lt","lte","in","contains"} or len(args) != 2:
        raise ValueError(f"unknown rule operation: {op}")
    left, right = map(value, args)
    operations = {"eq":lambda:left==right,"ne":lambda:left!=right,"gt":lambda:left>right,"gte":lambda:left>=right,"lt":lambda:left<right,"lte":lambda:left<=right,"in":lambda:left in right,"contains":lambda:right in left}
    try:
        result = bool(operations[op]())
    except TypeError as exc:
        raise ValueError(f"invalid operands for {op}") from exc
    return RuleResult(result, (f"{op}({left!r},{right!r})={result}",))

def effects(rules, data):
    result, trace = {}, []
    for rule in rules:
        evaluated = evaluate_condition(rule.when, data)
        trace.extend(evaluated.trace)
        if evaluated.value:
            result[rule.target] = rule.effect
    return result, trace
