from project_file_platform.api.main import run as run_api
from project_file_platform.mcp.server import run as run_mcp


def main() -> None:
    run_api()


__all__ = ["main", "run_api", "run_mcp"]
