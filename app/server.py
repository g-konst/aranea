from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import app.generated.parse_pb2 as parse_pb2

from app.config import settings
from app.logger import log, setup_logger
from app.manager import start_manager_server
from app.registry import WorkerRegistry

setup_logger()

worker_registry: Optional[WorkerRegistry] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_registry

    server, worker_registry = await start_manager_server(
        settings.server.manager_address
    )
    yield

    log.info("Shutting down all workers")
    worker_ids = list(worker_registry.processes.keys())
    for worker_id in worker_ids:
        try:
            await worker_registry.kill_worker(worker_id)
        except Exception as e:
            log.error(f"Error shutting down worker {worker_id}: {e}")

    await server.stop(grace=5)


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ActionArgument(BaseModel):
    name: str
    int_value: Optional[int] = None
    string_value: Optional[str] = None
    double_value: Optional[float] = None


class Action(BaseModel):
    func: str
    args: Optional[list[ActionArgument]] = []


class ParseRequest(BaseModel):
    url: str
    proxy: Optional[str] = ""
    timeout: Optional[int] = 10000
    actions: Optional[list[Action]] = []
    headers: Optional[dict[str, str]] = {}
    load: Optional[str] = "networkidle"
    block: Optional[list] = []


class ParseResponse(BaseModel):
    status: int
    content: str
    error: str
    headers: dict[str, str]
    cookies: list[dict]


@app.get("/")
async def get_dashboard():
    return FileResponse("app/static/dashboard/index.html")


@app.post("/spawn")
async def spawn_worker():
    try:
        result = await worker_registry.spawn_worker()
        return {
            "message": f"Worker {result['worker_id']} spawned on port {result['port']}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/worker/{worker_id}")
async def kill_worker(worker_id: str):
    try:
        return await worker_registry.kill_worker(worker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Worker not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workers")
async def list_workers():
    workers_list = []
    for worker_id, info in worker_registry.workers.items():
        workers_list.append(
            {
                "id": worker_id,
                "host": info["host"],
                "port": info["port"],
                "status": info["status"],
                "last_report": info["last_report"].isoformat(),
                "active_pages": info["active_pages"],
                "cpu_usage": info["cpu_usage"],
                "memory_usage": info["memory_usage"],
            }
        )
    return {"workers": workers_list}


@app.post("/parse")
async def parse(request: ParseRequest) -> ParseResponse:
    try:
        stub = await worker_registry.get_available_worker()
        log.info(f"Sending parse request to worker {stub}")
        grpc_request = parse_pb2.ParseRequest(
            **request.model_dump(exclude_defaults=True)
        )

        grpc_response = await stub.Parse(grpc_request)
        cookies = [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires,
                "httpOnly": cookie.http_only,
                "secure": cookie.secure,
                "sameSite": cookie.same_site,
            }
            for cookie in grpc_response.cookies
        ]
        return ParseResponse(
            status=grpc_response.status,
            content=grpc_response.content,
            headers=grpc_response.headers,
            cookies=cookies,
            error=grpc_response.error,
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error(f"Error parsing URL {request.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host=settings.server.host,
        port=settings.server.port,
    )
