# LicenseGuard (MCP)

LicenseGuard is designed to help you easily understand the software licenses of your project's dependencies.

Here's what it offers:

- **Effortless License Checking**: Simply provide your project's `requirements.txt`, and LicenseGuard will analyze it for you.
- **Clear License Identification**: The system identifies the software licenses associated with your dependencies.
- **Understandable Reports**: Get a straightforward JSON report detailing the licenses found, along with a confidence score.
- **Simple Integration**: You can interact with LicenseGuard through a user-friendly API to submit your dependency list and retrieve the analysis results.

LicenseGuard simplifies the process of checking software licenses, giving you a quick and clear picture of your project's licensing landscape.

---

## About This Repository

This repository contains the source code for the **MCP server**, which is responsible for processing and analyzing the licenses of your project's dependencies.

### Key Points:
1. The MCP server relies on an existing **REST-server** to function. The REST-server is available in a separate repository (https://github.com/cassiama/LicenseGuard-API).
2. You must ensure that the REST-server is running before starting the MCP server. The MCP server communicates with the REST-server to fetch and process data.
3. For more details about the REST-server, refer to its repository: [REST-server Repository](https://github.com/cassiama/LicenseGuard-API).
4. There is a sample **Agent** that includes an MCP-Client available in this repository: [LicenseGuard-AI](https://github.com/cassiama/LicenseGuard-AI). You can use this sample agent to test the MCP server.
5. Alternatively, you can use any off-the-shelf MCP-server tester to test the MCP server.

---

## Quickstart

The fastest and easiest way to get this running on your machine is to use Docker.

### Requirements

In short:

- Have Docker Desktop/Engine installed on your local machine.
- Ensure the REST-server is running and accessible.
- Set the required environment variables for calling the backend API server's URL.

---

Make sure you have Docker Desktop (or Docker Engine) installed on your machine. If you don't, download it from [Docker's website](https://docs.docker.com/get-started/get-docker/).

#### Environment Variables

You will need to provide the following, otherwise the server will fail to run and you will see errors:

- `BACKEND_URL_HOST`: Refers to the host that your backend REST API server is running on. Your host should be an HTTP/HTTPS domain (e.g., `http://localhost`).
- `BACKEND_URL_PORT`: Refers to the port that your REST-server is running on. Your port should be a number from 0 to 65535 (16-bit number) that **doesn't** conflict with a port already in use on the computer.

---

### Usage

For the purposes of this guide, we're going to assume that you want to pull the image from Docker Hub. However, you can also download the image from the GitHub Container Registry (GHCR) instead if you'd like.

#### Downloading the Docker Image

Run the following command to download the image from Docker Hub on your machine:

```bash
docker pull licenseguard/license-guard:mcp-latest
```

> NOTE: If you want a specific version, then pull the `licenseguard/license-guard:mcp-v{x.y.z}` image instead (`x.y.z` refers to the [semantic versioning number](https://semver.org/)).

> NOTE: For those who prefer GHCR, replace any reference to `licenseguard/license-guard` with `ghcr.io/cassiama/license-guard` for any of the commands below, and you'll be good. 👍🏿

---

#### Building the Docker Image Locally

If you'd like to build the Docker image from the source code, follow these steps:

1. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/your-repo/LicenseGuard-MCP.git
   cd LicenseGuard-MCP
   ```

2. Build the Docker image:
   ```bash
   docker build -t licenseguard/license-guard:mcp-latest .
   ```

   > NOTE: Replace `mcp-latest` with a specific version tag (e.g., `mcp-v1.0.0`) if needed.

3. Run the Docker image:
   - **With `.env` file:**
     ```bash
     docker run -p 8000:8000 --env-file .env licenseguard/license-guard:mcp-latest
     ```
   - **With environment variables:**
     ```bash
     docker run -p 8000:8000 -e BACKEND_URL_HOST=http://localhost -e BACKEND_URL_PORT=80 licenseguard/license-guard:mcp-latest
     ```

Once you get the server running, you can access all of the MCP-related resources at `http://localhost:8000/mcp`.

---

#### Running the MCP Server

To run the MCP server, follow these steps:

1. **Start the REST-server**:
   - Clone the REST-server repository and follow its setup instructions.
   - Ensure the REST-server is running and accessible at the host and port specified in the `BACKEND_URL_HOST` and `BACKEND_URL_PORT` environment variables.

2. **Run the MCP server**:
   - Use the Docker image or build it locally as described above.
   - Ensure the environment variables point to the running REST-server.

Once both servers are running, you can access all MCP-related resources at `http://localhost:8000/mcp`.

---

#### Testing the MCP Server

You can test the MCP server using one of the following methods:

1. **Using the Sample Agent**:
   - A sample agent with an MCP-Client is available in the [LicenseGuard-AI repository](https://github.com/cassiama/LicenseGuard-AI).
   - Clone the repository and follow the instructions to set up and run the agent.
   - The agent will interact with the MCP server and provide test results.

2. **Using an Off-the-Shelf MCP-Server Tester**:
   - You can use any standard MCP-server testing tool to verify the functionality of the MCP server.
   - Ensure the tester is configured to communicate with the MCP server at the correct host and port.

---



