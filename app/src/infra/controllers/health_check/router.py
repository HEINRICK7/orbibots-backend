from fastapi import APIRouter


class HealthCheckRouter:
    def __init__(self) -> None:
        self.router = APIRouter()
        self.router.add_api_route(
            "/health",
            self.health,
            methods=["GET"],
            tags=["health"],
        )

    def health(self) -> dict[str, str]:
        return {"status": "ok"}
