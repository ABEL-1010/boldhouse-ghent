from agent.tool_definitions import build_tool_definitions
from sentinel.features.events import ToolName


def test_one_definition_per_tool_with_description() -> None:
    definitions = build_tool_definitions()

    assert [d["name"] for d in definitions] == [tool.value for tool in ToolName]
    assert all(d["description"] for d in definitions)


def test_input_schemas_are_strict_objects() -> None:
    by_name = {d["name"]: d["input_schema"] for d in build_tool_definitions()}

    for schema in by_name.values():
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
    assert by_name["read_file"]["required"] == ["path"]
    assert set(by_name["send_email"]["required"]) == {"to", "subject", "body"}
    assert "required" not in by_name["list_dir"]  # path defaults to "."
