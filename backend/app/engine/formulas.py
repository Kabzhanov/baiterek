from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

def dependencies(expr: Any) -> set[str]:
    if isinstance(expr, str) and expr.startswith("$"): return {expr[1:]}
    if isinstance(expr, dict): return set().union(*(dependencies(v) for v in expr.values()))
    if isinstance(expr, list): return set().union(*(dependencies(v) for v in expr))
    return set()

def topological_order(graph: dict[str, set[str]]) -> list[str]:
    graph, result = {k:set(v) for k,v in graph.items()}, []
    while graph:
        ready = sorted(k for k,v in graph.items() if not v)
        if not ready: raise ValueError("formula dependency cycle")
        result.extend(ready)
        for key in ready: graph.pop(key)
        for deps in graph.values(): deps.difference_update(ready)
    return result

def evaluate_formula(expr: Any, data: dict[str, Any]):
    trace = []
    def evaluate(item):
        if isinstance(item, str) and item.startswith("$"):
            key = item[1:]
            if key not in data: raise ValueError(f"unknown value: {key}")
            return Decimal(str(data[key])) if isinstance(data[key], (int,float,Decimal)) else data[key]
        if not isinstance(item, dict): return Decimal(str(item)) if isinstance(item,(int,float,Decimal)) and not isinstance(item,bool) else item
        op = item.get("op"); args = [evaluate(a) for a in item.get("args", [])]
        if op == "add": result = sum(args, Decimal(0))
        elif op == "sub": result = args[0] - args[1]
        elif op == "mul":
            result = Decimal(1)
            for arg in args: result *= arg
        elif op == "div": result = args[0] / args[1]
        elif op == "sum": result = sum((Decimal(str(v)) for v in args[0]), Decimal(0))
        elif op == "min": result = min(args)
        elif op == "max": result = max(args)
        elif op == "round": result = args[0].quantize(Decimal(1).scaleb(-int(args[1])), rounding=ROUND_HALF_UP)
        elif op == "if": result = args[1] if bool(args[0]) else args[2]
        elif op == "annuity":
            principal, annual, months = args; rate = annual / Decimal(12); count = int(months)
            result = principal / months if rate == 0 else principal*rate*(1+rate)**count/((1+rate)**count-1)
        else: raise ValueError(f"unknown formula operation: {op}")
        trace.append(f"{op}={result}"); return result
    try: return evaluate(expr), trace
    except (ZeroDivisionError, InvalidOperation) as exc: raise ValueError("formula division by zero") from exc
