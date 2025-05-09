import grpc

import app.generated.parse_pb2 as parse_pb2
import app.generated.parse_pb2_grpc as parse_pb2_grpc

from app.logger import log
from app.registry import WorkerRegistry


class ParserManagerServicer(parse_pb2_grpc.ParserManagerServicer):
    def __init__(self, worker_registry):
        self.worker_registry = worker_registry

    async def RegisterWorker(self, request, context):
        worker_id = request.worker_id
        port = request.port
        host = request.host

        log.info(f"Worker {worker_id} registering from {host}:{port}")
        await self.worker_registry.register_worker(worker_id, host, port)
        return parse_pb2.RegistrationResponse(
            success=True, message=f"Worker {worker_id} registered successfully"
        )

    async def ReportStatus(self, request, context):
        worker_id = request.worker_id
        status = request.status
        port = request.port

        await self.worker_registry.update_worker_status(
            worker_id,
            port,
            status,
            request.active_pages,
            request.cpu_usage,
            request.memory_usage,
        )

        return parse_pb2.StatusAck(received=True, message="Status updated")


async def start_manager_server(address):
    server = grpc.aio.server()
    worker_registry = WorkerRegistry()
    servicer = ParserManagerServicer(worker_registry)
    parse_pb2_grpc.add_ParserManagerServicer_to_server(servicer, server)
    server.add_insecure_port(address)
    await server.start()
    log.info(f"Manager server started on: {address}")
    return server, worker_registry
