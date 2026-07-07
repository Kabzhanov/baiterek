from decimal import Decimal
from app.engine.formulas import dependencies, evaluate_formula, topological_order
from app.engine.rules import effects, evaluate_condition

def compute(definition, data):
    values, explanations = dict(data), {}; formulas = {c.key:c for c in definition.computed}
    graph = {key:dependencies(item.expression)&set(formulas) for key,item in formulas.items()}
    for key in topological_order(graph): values[key], explanations[key] = evaluate_formula(formulas[key].expression, values)
    return values, explanations

def validate(definition, data, full=True, delta_keys=None):
    applied, _ = effects(definition.rules, data); errors = []
    for stage in definition.stages:
        for step in stage.steps:
            for field in step.fields:
                if delta_keys is not None and field.key not in delta_keys: continue
                visible = applied.get(field.key) != "hide"
                required = (field.required or applied.get(field.key) == "require") and applied.get(field.key) != "optional"
                value = data.get(field.key)
                if full and visible and required and value in (None,"",[]): errors.append({"field":field.key,"code":"required"})
                if value is not None and field.type == "number":
                    if field.minimum is not None and value < field.minimum: errors.append({"field":field.key,"code":"minimum"})
                    if field.maximum is not None and value > field.maximum: errors.append({"field":field.key,"code":"maximum"})
    return errors

def render(definition, data, checkpoint=None, user_context=None):
    checkpoint = checkpoint or {}; values, explanations = compute(definition, data); applied, trace = effects(definition.rules, values)
    stage_index, step_index = checkpoint.get("stage",0), checkpoint.get("step",0); step = definition.stages[stage_index].steps[step_index]
    fields = [{"key":f.key,"type":f.type,"label":f.label,"visible":applied.get(f.key)!="hide","required":(f.required or applied.get(f.key)=="require") and applied.get(f.key)!="hide","enabled":applied.get(f.key)!="disable"} for f in step.fields]
    chunks = [fields[i:i+6] for i in range(0,len(fields),6)] or [[]]; screen = min(checkpoint.get("screen",0),len(chunks)-1)
    return {"stage":definition.stages[stage_index].key,"step":step.key,"screen":screen,"fields":chunks[screen],"computed":{k:str(v) if isinstance(v,Decimal) else v for k,v in values.items() if k not in data},"validation":validate(definition,values),"progress":{"current":step_index+1,"total":sum(len(s.steps) for s in definition.stages)},"explanations":{"rules":trace,"computed":explanations}}

def transition(definition, current, target, data):
    candidates = [t for t in definition.transitions if t.source==current and t.target==target]
    if not candidates: raise ValueError("transition is not allowed")
    if candidates[0].when and not evaluate_condition(candidates[0].when,data).value: raise ValueError("transition condition failed")
    return target
