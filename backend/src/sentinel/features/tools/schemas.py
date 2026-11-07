from pydantic import BaseModel, ConfigDict, Field

from sentinel.features.events import ToolName


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadFileArgs(ToolArgs):
    path: str = Field(description="File path relative to the workspace root.")


class WriteFileArgs(ToolArgs):
    path: str = Field(description="File path relative to the workspace root.")
    content: str = Field(description="Full text content to write. Overwrites existing files.")


class DeleteFileArgs(ToolArgs):
    path: str = Field(description="File path relative to the workspace root.")


class ListDirArgs(ToolArgs):
    path: str = Field(default=".", description="Directory relative to the workspace root.")


class FetchUrlArgs(ToolArgs):
    url: str = Field(description="URL of the web page to fetch.")


class SendEmailArgs(ToolArgs):
    to: str = Field(description="Recipient email address.")
    subject: str
    body: str


class HttpPostArgs(ToolArgs):
    url: str = Field(description="Destination URL.")
    data: str = Field(description="Request body, e.g. a JSON string.")


TOOL_ARGS: dict[ToolName, type[ToolArgs]] = {
    ToolName.READ_FILE: ReadFileArgs,
    ToolName.WRITE_FILE: WriteFileArgs,
    ToolName.DELETE_FILE: DeleteFileArgs,
    ToolName.LIST_DIR: ListDirArgs,
    ToolName.FETCH_URL: FetchUrlArgs,
    ToolName.SEND_EMAIL: SendEmailArgs,
    ToolName.HTTP_POST: HttpPostArgs,
}


class ToolOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    content: str
