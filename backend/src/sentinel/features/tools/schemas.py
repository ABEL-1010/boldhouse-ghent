from pydantic import BaseModel, ConfigDict, Field

from sentinel.features.events import ToolName


class ToolArgs(BaseModel):
    """Base for tool arguments. The docstring of each subclass is the tool description."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadFileArgs(ToolArgs):
    """Read a text file from the workspace and return its contents."""

    path: str = Field(description="File path relative to the workspace root.")


class WriteFileArgs(ToolArgs):
    """Create or overwrite a text file in the workspace. Parent folders are created."""

    path: str = Field(description="File path relative to the workspace root.")
    content: str = Field(description="Full text content to write. Overwrites existing files.")


class DeleteFileArgs(ToolArgs):
    """Delete a single file from the workspace. Folders cannot be deleted."""

    path: str = Field(description="File path relative to the workspace root.")


class ListDirArgs(ToolArgs):
    """List the files and folders in a workspace directory. Folders end with "/"."""

    path: str = Field(default=".", description="Directory relative to the workspace root.")


class FetchUrlArgs(ToolArgs):
    """Fetch a web page and return its raw HTML."""

    url: str = Field(description="URL of the web page to fetch.")


class SendEmailArgs(ToolArgs):
    """Send an email."""

    to: str = Field(description="Recipient email address.")
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Plain-text email body.")


class HttpPostArgs(ToolArgs):
    """Send an HTTP POST request with a text body to a URL."""

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
