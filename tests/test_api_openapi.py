from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.openapi import configure_api_openapi
from app.api.router import create_api_router
from app.routes import create_router


def _app_with_mixed_routes(http_prefix: str = ""):
    api_base = f"{http_prefix}/api"
    app = FastAPI(
        title="IMPulse",
        version="1.0.0",
        docs_url=f"{api_base}/docs",
        redoc_url=None,
        openapi_url=f"{api_base}/openapi.json",
    )
    router = APIRouter(prefix=http_prefix)

    @router.get("/metrics")
    async def metrics():
        return {"ok": True}

    @router.get("/api/incidents")
    async def incidents():
        return {}

    @router.get("/api/groups")
    async def groups():
        return {}

    app.include_router(router)
    configure_api_openapi(app, http_prefix)
    return app, api_base


def test_swagger_ui_served():
    app, api_base = _app_with_mixed_routes()
    client = TestClient(app)

    response = client.get(f"{api_base}/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_redoc_disabled():
    app, api_base = _app_with_mixed_routes()
    client = TestClient(app)

    assert client.get(f"{api_base}/redoc").status_code == 404


def test_openapi_schema_only_includes_api_paths():
    app, api_base = _app_with_mixed_routes()
    client = TestClient(app)

    schema = client.get(f"{api_base}/openapi.json").json()
    paths = set(schema["paths"])

    assert paths == {f"{api_base}/incidents", f"{api_base}/groups"}
    assert "/metrics" not in paths


def test_openapi_schema_respects_http_prefix():
    app, api_base = _app_with_mixed_routes(http_prefix="/impulse")
    client = TestClient(app)

    schema = client.get(f"{api_base}/openapi.json").json()
    paths = set(schema["paths"])

    assert paths == {"/impulse/api/incidents", "/impulse/api/groups"}
    assert "/impulse/metrics" not in paths


def test_openapi_keeps_status_codes_without_schemas():
    app = FastAPI(
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(create_api_router())
    configure_api_openapi(app, "")

    schema = TestClient(app).get("/api/openapi.json").json()
    assert "components" not in schema
    assert schema["paths"]["/api/incidents"]["get"]["responses"] == {
        "200": {"description": "Successful Response"},
    }
    assert schema["paths"]["/api/incidents/{uniq_id}"]["get"]["responses"] == {
        "200": {"description": "Successful Response"},
        "404": {"description": "Incident not found"},
    }
    for path, methods in schema["paths"].items():
        assert "422" not in methods["get"]["responses"], path
        for body in methods["get"]["responses"].values():
            assert "content" not in body, path


def test_openapi_documents_action_bodies_and_validation():
    app = FastAPI()
    app.include_router(create_router("/impulse"))
    configure_api_openapi(app, "/impulse")

    schema = app.openapi()
    assert app.openapi() is schema
    for action, model in [("assign", "AssignmentRequest"), ("freeze", "FreezeRequest")]:
        operation = schema["paths"][f"/impulse/api/incidents/{{uniq_id}}/{action}"]["post"]
        assert operation["requestBody"]["required"]
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert ref == f"#/components/schemas/{model}"
        assert model in schema["components"]["schemas"]
        assert "422" in operation["responses"]
    assert schema["components"]["schemas"]["FreezeRequest"]["properties"]["until"]["format"] == "date-time"
    for action in ["task", "unassign", "unfreeze"]:
        operation = schema["paths"][f"/impulse/api/incidents/{{uniq_id}}/{action}"]["post"]
        assert "requestBody" not in operation
        assert "422" not in operation["responses"]
