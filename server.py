import os
import httpx
from dotenv import load_dotenv
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "LicenseGuard-MCP-Server",
    stateless_http=True,    # needed for streaming stability (source: https://dev.to/andreasbergstrom/using-fastmcp-with-openai-and-avoiding-session-termination-issues-k3h)
)

POST_ROUTE_TIMEOUT = 60
MAX_RETRIES = 3


# import the environment variables
load_dotenv()
BACKEND_URL_HOST = os.getenv("BACKEND_URL_HOST")
BACKEND_URL_PORT = os.getenv("BACKEND_URL_PORT")
MCP_URL_HOST = os.getenv("MCP_URL_HOST")
MCP_URL_PORT = os.getenv("MCP_URL_PORT")


class Token(BaseModel):
    access_token: str
    token_type: str


@mcp.tool()
def analyze_dependencies(
    project_name: str,
    requirements_content: str,
    user_token: str
):
    # validate the project name according to the 'DependencyReport' schema (see LicenseGuard-API)
    assert isinstance(project_name, str), "The project name must be of type string."
    if len(project_name) < 1 or len(project_name) > 100:
        raise RuntimeError("Project name must be between 1 and 100 characters.")

    # validate the requirements.txt content
    assert isinstance(
        requirements_content, str), "The 'requirements.txt' file must be of type string."

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
                    # headers={"Authorization": f"Bearer {token.access_token}"},
                    headers={"Authorization": f"Bearer {user_token}"},
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



if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
    )
