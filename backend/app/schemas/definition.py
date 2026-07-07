from __future__ import annotations
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.engine.formulas import dependencies, topological_order

class FieldBase(BaseModel):
    key: str
    label: str
    topic: str = "main"
    required: bool = False

class TextField(FieldBase):
    type: Literal["text"]

class NumberField(FieldBase):
    type: Literal["number"]
    minimum: float | None = None
    maximum: float | None = None

class BooleanField(FieldBase):
    type: Literal["boolean"]

class SelectField(FieldBase):
    type: Literal["select"]
    options: list[str]

class RepeaterField(FieldBase):
    type: Literal["repeater"]

FieldType = Annotated[TextField|NumberField|BooleanField|SelectField|RepeaterField, Field(discriminator="type")]

class Step(BaseModel):
    key: str
    title: str
    fields: list[FieldType]

class Stage(BaseModel):
    key: str
    title: str
    steps: list[Step]

class Rule(BaseModel):
    target: str
    effect: Literal["show","hide","require","optional","enable","disable"]
    when: dict

class Computed(BaseModel):
    key: str
    expression: dict

class Transition(BaseModel):
    source: str
    target: str
    when: dict | None = None

class Meta(BaseModel):
    title: str
    description: str = ""

class ServiceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    service_id: str
    version: int = 1
    meta: Meta
    stages: list[Stage]
    rules: list[Rule] = Field(default_factory=list)
    computed: list[Computed] = Field(default_factory=list)
    statuses: list[str]
    transitions: list[Transition] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        stages = [s.key for s in self.stages]
        steps = [p.key for s in self.stages for p in s.steps]
        fields = [f.key for s in self.stages for p in s.steps for f in p.fields]
        computed = [c.key for c in self.computed]
        for values, label in ((stages,"stage"),(steps,"step"),(fields+computed,"field"),(self.statuses,"status")):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} key")
        known = set(fields + computed)
        unknown = {r.target for r in self.rules} - known
        if unknown:
            raise ValueError(f"unknown rule targets: {sorted(unknown)}")
        if any(t.source not in self.statuses or t.target not in self.statuses for t in self.transitions):
            raise ValueError("transition references unknown status")
        graph = {c.key: dependencies(c.expression) & set(computed) for c in self.computed}
        topological_order(graph)
        refs = set().union(*(dependencies(c.expression) for c in self.computed)) if self.computed else set()
        if refs - known:
            raise ValueError(f"unknown formula references: {sorted(refs-known)}")
        return self
