import os
import httpx
from typing import Any
from datetime import datetime
from secrets import token_hex
from dotenv import load_dotenv
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LicenseGuard-MCP")

POST_ROUTE_TIMEOUT = 60
MAX_RETRIES = 3


# import the environment variables
load_dotenv()
BACKEND_URL_HOST = os.getenv("BACKEND_URL_HOST")
BACKEND_URL_PORT = os.getenv("BACKEND_URL_PORT")
MCP_URL_HOST = os.getenv("MCP_URL_HOST")
MCP_URL_PORT = os.getenv("MCP_URL_PORT")
MCP_CLIENT_ID = os.getenv("MCP_CLIENT_ID", "mcp-server")
MCP_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", token_hex(16))


class Token(BaseModel):
    access_token: str
    token_type: str

def get_access_token() -> Token:
    # verify that the MCP client ID and secret were provided
    assert MCP_CLIENT_ID is not None, "MCP_CLIENT_ID must be provided to authenticate the MCP server."
    assert MCP_CLIENT_SECRET is not None, "MCP_CLIENT_SECRET must be provided to authenticate the MCP server."

    with httpx.Client() as client:
        for attempt in range(MAX_RETRIES):
            try:
                # call the backend API (will not work if it's not alive!)
                form_data = {
                    "client_id": MCP_CLIENT_ID,
                    "client_secret": MCP_CLIENT_SECRET,
                    # "scopes": ""
                }
                resp = client.post(
                    f"{BACKEND_URL_HOST}:{BACKEND_URL_PORT}/mcp/token",
                    data=form_data,
                    timeout=POST_ROUTE_TIMEOUT
                )

                # raise an exception if the server returned an error code of some sort
                resp.raise_for_status()

                # otherwise, convert the JSON of the server's response to a Token
                json: dict[str, Any] = resp.json()
                # raise RuntimeError(f"This is the culprit: {json.get("access_token")}")
                return Token(access_token=json.get("access_token", ""), token_type=json.get("token_type", "bearer"))

            except httpx.RequestError as exc:
                # print(f"An error occurred while requesting {exc.request.url!r}.")
                raise RuntimeError(
                    f"An error occurred while requesting {exc.request.url!r}.")
            except httpx.HTTPStatusError as exc:
                # print(
                    # f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
                raise RuntimeError(
                    f"(Attempt {attempt+1}) Received {exc.response.status_code}: {exc.response.json().get("detail", "An unknown error occurred.")}")


@mcp.tool()
def analyze_dependencies(
    project_name: str,
    requirements_content: str
):
    # validate the project name according to the 'DependencyReport' schema (see LicenseGuard-API)
    assert type(project_name) == str, "The project name must be of type string."
    if len(project_name) < 1 or len(project_name) > 100:
        raise RuntimeError("Project name must be between 1 and 100 characters.")

    # validate the requirements.txt content
    assert type(
        requirements_content) == str, "The 'requirements.txt' file must be of type string."

    # get the JWT token by calling the authorization route for the MCP server
    token = get_access_token()
    assert token.token_type.lower() == "bearer", "The token must be of the 'bearer' type."
    if not token.access_token:
        raise RuntimeError("The JWT failed to be obtained from the backend server.")

    # "create" the requirements.txt file for the POST request to the backend
    requirements_file = (
        f"{project_name}_requirements.txt",
        requirements_content.encode("utf-8"),
        "text/plain"
    )
    files = {"file": requirements_file}
    # create the form data for the POST request
    data = {"project_name": project_name}

    with httpx.Client() as client:
        for attempt in range(MAX_RETRIES):
            try:
                # call the backend API (will not work if it's not alive!)
                resp = client.post(
                    f"{BACKEND_URL_HOST}:{BACKEND_URL_PORT}/analyze",
                    headers={"Authorization": f"Bearer {token.access_token}"},
                    data=data,
                    files=files,
                    timeout=POST_ROUTE_TIMEOUT
                )

                # raise an exception if the server returned an error code of some sort
                resp.raise_for_status()

                # otherwise, return a JSON of the server's response (should correspond to `AnalyzeResult` in the API's 'schemas.py' file)
                return resp.json()
            except httpx.RequestError as exc:
                # print(f"An error occurred while requesting {exc.request.url!r}.")
                raise RuntimeError(
                    f"An error occurred while requesting {exc.request.url!r}.")
            except httpx.HTTPStatusError as exc:
                # print(
                #     f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
                raise RuntimeError(
                    f"(Attempt {attempt+1}) Received {exc.response.status_code}: {exc.response.json().get("detail", "An unknown error occurred.")}")


@mcp.tool("get_time")
def get_time() -> datetime:
    return datetime.now()


if __name__ == "__main__":
    # print("🚀 Starting the MCP server...")
    mcp.run(
        transport="streamable-http",
    )
