from __future__ import annotations
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.engine.formulas import dependencies, topological_order

class FieldBase(BaseModel):
    key: str
    label: str
    topic: str = "main"
    required: bool = False
    # SPEC.md §4.3 "Предзаполнение из mock-ГБД ЮЛ по БИН" / "Обязательное расширение" §1
    # "Ничего не спрашиваем, если можем узнать сами". Purely declarative — the engine
    # never reads `prefill`/`hint` (same "engine is dumb, Definition carries the
    # meaning" pattern as `rules`/`computed`); `engine.runtime.render()` only ferries
    # them through to the screen contract so the frontend knows what to do.
    #
    # `prefill` convention (documented here + docs/service-definition.md):
    #   - Trigger field (the BIN input the user actually types):
    #       "prefill": "gbd_ul.lookup"
    #     On input/blur the frontend calls `GET /integrations/gbd-ul/{value}` and
    #     distributes the response over the target fields below.
    #   - Target fields (auto-filled from the lookup response, shown collapsed as a
    #     summary per "Обязательное расширение" §1, editable if the user disagrees):
    #       "prefill": "gbd_ul.name"        <- GbdUlOut.name
    #       "prefill": "gbd_ul.address"     <- GbdUlOut.address
    #       "prefill": "gbd_ul.oked"        <- GbdUlOut.oked
    #       "prefill": "gbd_ul.oked_name"   <- GbdUlOut.oked_name
    #       "prefill": "gbd_ul.director"    <- GbdUlOut.director
    # `hint` is a free-text plain-language tip shown next to the field (SPEC.md §5.2
    # "Редактор поля: тип, label, hint, ..."), independent of whether `prefill` is set.
    prefill: str | None = None
    hint: str | None = None

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
    # Человеческие подписи статусов для ЛК (SPEC §3 "statuses.labels_plain", §4.4 статус-бейдж);
    # статусы без подписи фронт показывает через свой fallback-словарь.
    labels_plain: dict[str, str] = Field(default_factory=dict)

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
