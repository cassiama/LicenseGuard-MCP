# LicenseGuard (MCP)

LicenseGuard is designed to help you easily understand the software licenses of your project's dependencies.

Here's what it offers:

- **Effortless License Checking**: Simply provide your project's `requirements.txt`, and LicenseGuard will analyze it for you.
- **Clear License Identification**: The system identifies the software licenses associated with your dependencies.
- **Understandable Reports**: Get a straightforward JSON report detailing the licenses found, along with a confidence score.
- **Simple Integration**: You can interact with LicenseGuard through a user-friendly API to submit your dependency list and retrieve the analysis results.

LicenseGuard simplifies the process of checking software licenses, giving you a quick and clear picture of your project's licensing landscape.

## Quickstart

The fastest and easiest way to get this running on your machine is to use Docker.

### Requirements

In short:

- have Docker Desktop/Engine installed on your local machine
- environment variables for calling the backend API server's URL

---

Make sure you have Docker Desktop (or Docker Engine) installed on your machine. If you don't, download it from [Docker's website](https://docs.docker.com/get-started/get-docker/).

#### Environment Variables

You will need to provide the following, otherwise the server will fail to run and you will see errors:

- `BACKEND_URL_HOST`: refers to the host that your backend REST API server is running on. Your host should be a HTTP/HTTPS domain (e.g. `http://localhost`).
- `BACKEND_URL_PORT`: refers to the port that your MCP server is running on. Your port should be a number from 0 to 65535 (16-bit number) that **doesn't** conflict with a port already in use on the computer.

### Usage

For the purposes of this guide, we're going to assume that you want to pull the image from Docker Hub. However, you can also download the image from the GitHub Container Registry (GHCR) instead if you'd like.

#### Downloading the Docker Image

Run the following command to download the image from Docker Hub on your machine:

```bash
docker pull licenseguard/license-guard:mcp-latest
```

> NOTE: If you want a specific version, then pull the `licenseguard/license-guard:mcp-v{x.y.z}` image instead (`x.y.z` refers to the [semantic verisoning number](https://semver.org/)).

> NOTE: For those who prefer GHCR, replace any reference to `licenseguard/license-guard` with `ghcr.io/cassiama/license-guard` for any of the commands below, and you'll be good. 👍🏿

#### Running the Docker Image

- **With `.env` file:**
Run the Docker image by running `docker run -p 8000:8000 --env-file .env licenseguard/license-guard:mcp-latest` in the terminal.

- **With an environment variable:**
Run the Docker image by running `docker run -p 8000:8000 -e BACKEND_URL_HOST=http://localhost -e BACKEND_URL_PORT=80 licenseguard/license-guard:mcp-latest` in the terminal.

Once you get the server running, you can access all of the MCP-related resources at `http://localhost:8000/mcp`.
