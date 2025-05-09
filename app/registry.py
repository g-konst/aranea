import asyncio
import subprocess
from datetime import datetime

import grpc

import app.generated.parse_pb2 as parse_pb2
import app.generated.parse_pb2_grpc as parse_pb2_grpc

from app.config import settings
from app.logger import log


class WorkerRegistry:
    def __init__(self):
        self.workers = {}
        self.processes = {}
        self._lock = asyncio.Lock()
        self._worker_id_counter = 0
        self._base_port = 50051

    async def spawn_worker(self):
        async with self._lock:
            worker_id = f"worker-{self._worker_id_counter}"
            port = self._base_port + self._worker_id_counter
            self._worker_id_counter += 1

            cmd = [
                "python",
                "app/grpc/worker.py",
                "--id",
                worker_id,
                "--port",
                str(port),
                "--manager",
                settings.server.manager_address,
            ]

            log.info(f"Spawning worker {worker_id} on port {port}...")
            proc = subprocess.Popen(cmd)

            self.processes[worker_id] = {
                "process": proc,
                "port": port,
                "spawn_time": datetime.now(),
                "registered": False,
            }

            for _ in range(30):  # 30 seconds timeout
                await asyncio.sleep(1)
                if worker_id in self.workers and self.workers[worker_id].get(
                    "registered", False
                ):
                    self.processes[worker_id]["registered"] = True
                    return {"worker_id": worker_id, "port": port}

            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            raise RuntimeError(
                f"Worker {worker_id} failed to register within timeout"
            )

    async def kill_worker(self, worker_id):
        async with self._lock:
            if worker_id not in self.processes:
                raise KeyError(f"Worker {worker_id} not found")

            process_info = self.processes[worker_id]
            process = process_info["process"]
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)

            if worker_id in self.workers:
                if "stub" in self.workers[worker_id] and hasattr(
                    self.workers[worker_id]["stub"], "_channel"
                ):
                    await self.workers[worker_id]["stub"]._channel.close()
                del self.workers[worker_id]

            del self.processes[worker_id]
            return {"worker_id": worker_id, "status": "terminated"}

    async def register_worker(self, worker_id, host, port):
        log.info(f"Worker {worker_id} registered from {host}:{port}")
        channel = grpc.aio.insecure_channel(f"{host}:{port}")
        stub = parse_pb2_grpc.ParserWorkerStub(channel)
        self.workers[worker_id] = {
            "host": host,
            "port": port,
            "stub": stub,
            "status": "UNKNOWN",
            "last_report": datetime.now(),
            "active_pages": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "registered": True,
        }

    async def update_worker_status(
        self, worker_id, port, status, active_pages, cpu_usage, memory_usage
    ):
        async with self._lock:
            if worker_id in self.workers:
                self.workers[worker_id]["status"] = status
                self.workers[worker_id]["last_report"] = datetime.now()
                self.workers[worker_id]["active_pages"] = active_pages
                self.workers[worker_id]["cpu_usage"] = cpu_usage
                self.workers[worker_id]["memory_usage"] = memory_usage

    async def get_available_worker(self):
        async with self._lock:
            available_workers = [
                (id, info)
                for id, info in self.workers.items()
                if info["status"] == parse_pb2.HealthCheckStatus.Value("OK")
            ]

            if not available_workers:
                raise RuntimeError("No healthy workers available")

            worker_id, info = min(
                available_workers,
                key=lambda x: (x[1]["active_pages"], x[1]["cpu_usage"]),
            )

            return info["stub"]
