from pathlib import Path
from typing import Any, Self

import httpx
from pydantic import ValidationError

from sentinel.core.config import Settings
from sentinel.features.events import ToolName
from sentinel.features.tools import filesystem, outbox, web
from sentinel.features.tools.errors import ToolError
from sentinel.features.tools.schemas import (
    TOOL_ARGS,
    DeleteFileArgs,
    FetchUrlArgs,
    HttpPostArgs,
    ListDirArgs,
    ReadFileArgs,
    SendEmailArgs,
    ToolArgs,
    ToolOutcome,
    WriteFileArgs,
)


class ToolService:
    """Runs sandboxed tools. Never raises for bad input: failures become ToolOutcome(ok=False)."""

    def __init__(
        self,
        workspace: Path,
        outbox_path: Path,
        fetch_base_url: str,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._workspace = workspace
        self._outbox_path = outbox_path
        self._fetch_base_url = fetch_base_url
        self._http_transport = http_transport

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(settings.runtime_workspace, settings.outbox_path, settings.fake_web_base_url)

    async def run(self, tool: str, args: dict[str, Any]) -> ToolOutcome:
        try:
            name = ToolName(tool)
        except ValueError:
            return ToolOutcome(ok=False, content=f"Unknown tool: '{tool}'.")
        try:
            parsed = TOOL_ARGS[name].model_validate(args)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, err['loc'])) or 'args'}: {err['msg']}" for err in exc.errors()
            )
            return ToolOutcome(ok=False, content=f"Invalid arguments for {name}: {problems}.")
        try:
            return ToolOutcome(ok=True, content=await self._dispatch(parsed))
        except ToolError as exc:
            return ToolOutcome(ok=False, content=str(exc))

    async def _dispatch(self, args: ToolArgs) -> str:
        match args:
            case ReadFileArgs(path=path):
                return filesystem.read_file(self._workspace, path)
            case WriteFileArgs(path=path, content=content):
                return filesystem.write_file(self._workspace, path, content)
            case DeleteFileArgs(path=path):
                return filesystem.delete_file(self._workspace, path)
            case ListDirArgs(path=path):
                return filesystem.list_dir(self._workspace, path)
            case FetchUrlArgs(url=url):
                return await web.fetch_url(url, self._fetch_base_url, self._http_transport)
            case SendEmailArgs(to=to, subject=subject, body=body):
                return outbox.send_email(self._outbox_path, to, subject, body)
            case HttpPostArgs(url=url, data=data):
                return outbox.http_post(self._outbox_path, url, data)
        raise AssertionError(f"No handler for {type(args).__name__}")
