from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def configure_api_openapi(app: FastAPI, http_prefix: str = "") -> None:
    """Limit the OpenAPI schema (and thus Swagger) to /api routes."""
    api_prefix = f"{http_prefix}/api"

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        openapi_schema["paths"] = {
            path: item
            for path, item in openapi_schema["paths"].items()
            if path == api_prefix or path.startswith(f"{api_prefix}/")
        }
        # Keep status codes for Swagger Try it out; drop schemas and unreachable 422.
        for path_item in openapi_schema["paths"].values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                operation["responses"] = {
                    code: {"description": body.get("description", "Response")}
                    for code, body in operation.get("responses", {}).items()
                    if code != "422" and isinstance(body, dict)
                }
        openapi_schema.pop("components", None)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
