from anthropic.types import ToolParam

from sentinel.features.tools import TOOL_ARGS


def build_tool_definitions() -> list[ToolParam]:
    """Anthropic tool definitions generated from Sentinel's argument models, so they never drift."""
    definitions: list[ToolParam] = []
    for name, args_model in TOOL_ARGS.items():
        description = (args_model.__doc__ or "").strip()
        if not description:
            raise ValueError(f"{args_model.__name__} needs a docstring: it is the tool description")
        definitions.append(
            {
                "name": name.value,
                "description": description,
                "input_schema": args_model.model_json_schema(),
            }
        )
    return definitions
