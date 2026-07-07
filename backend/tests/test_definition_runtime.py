import pytest
pytest.importorskip("pydantic")
from pydantic import ValidationError
from app.schemas.definition import ServiceDefinition
from app.engine.runtime import render, transition, validate

def definition(**updates):
    source={"service_id":"generic","meta":{"title":"Generic"},"statuses":["draft","submitted"],"transitions":[{"source":"draft","target":"submitted"}],"stages":[{"key":"stage","title":"Stage","steps":[{"key":"step","title":"Step","fields":[{"key":"name","label":"Name","type":"text","required":True},{"key":"age","label":"Age","type":"number","minimum":18}]}]}],"computed":[{"key":"double_age","expression":{"op":"mul","args":["$age",2]}}]}
    source.update(updates)
    return ServiceDefinition.model_validate(source)

def test_schema_round_trip_and_json_schema():
    item=definition()
    assert ServiceDefinition.model_validate_json(item.model_dump_json()) == item
    assert "schema_version" in ServiceDefinition.model_json_schema()["properties"]

def test_semantic_validation_rejects_bad_reference_and_cycle():
    with pytest.raises(ValidationError,match="unknown formula"):
        definition(computed=[{"key":"x","expression":{"op":"add","args":["$missing",1]}}])
    with pytest.raises(ValidationError,match="cycle"):
        definition(computed=[{"key":"x","expression":{"op":"add","args":["$y",1]}},{"key":"y","expression":{"op":"add","args":["$x",1]}}])

def test_render_validation_and_lifecycle_are_generic():
    item=definition()
    screen=render(item,{"age":20})
    assert screen["computed"]["double_age"] == "40" and len(screen["fields"]) <= 6
    assert validate(item,{"age":16}) == [{"field":"name","code":"required"},{"field":"age","code":"minimum"}]
    assert transition(item,"draft","submitted",{}) == "submitted"
    with pytest.raises(ValueError):
        transition(item,"submitted","draft",{})
