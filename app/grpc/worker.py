import argparse
import asyncio
import signal
from typing import Optional

import grpc
import psutil
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

import app.generated.parse_pb2 as parse_pb2
import app.generated.parse_pb2_grpc as parse_pb2_grpc

from app.config import settings
from app.logger import log, setup_logger


class Worker:
    def __init__(
        self, worker_id: int, manager_address: str, port: int
    ) -> None:
        self.worker_id = worker_id
        self.manager_address = manager_address
        self.port = port

        self.browser = None
        self.manager_channel = None
        self.manager_stub = None

        self._status_reporting_task = None
        self._camoufox: Optional[AsyncCamoufox] = None
        self._active_pages = 0
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def init_browser(self):
        if self.browser:
            return

        for attempt in range(settings.browser.max_retries):
            s_msg = f"(attempt {attempt + 1}/{settings.browser.max_retries})"
            try:
                log.info(f"Initializing browser {s_msg}")
                self._camoufox = AsyncCamoufox(
                    humanize=settings.browser.humanize,
                    headless=settings.browser.headless,
                    locale=settings.browser.locale,
                    block_webrtc=settings.browser.block_webrtc,
                    geoip=settings.browser.geoip,
                )
                self.browser = await asyncio.wait_for(
                    self._camoufox.__aenter__(),
                    timeout=settings.browser.launch_timeout / 1000,
                )
                log.info("Browser initialized successfully")
                return
            except Exception as e:
                log.error(f"Failed to initialize browser {s_msg}: {e}")
                if attempt < settings.browser.max_retries - 1:
                    await asyncio.sleep(settings.browser.retry_delay / 1000)
                else:
                    raise

    async def close_browser(self):
        if not self.browser:
            return

        log.info("Closing browser")
        try:
            await asyncio.wait_for(
                self.browser.__aexit__(None, None, None),
                timeout=settings.browser.close_timeout / 1000,
            )
            self.browser = None
            log.info("Browser closed successfully")
        except asyncio.TimeoutError:
            log.error("Timeout while closing browser")
            if self._camoufox:
                await self._camoufox.force_close()

    async def connect_to_manager(self):
        self.manager_channel = grpc.aio.insecure_channel(self.manager_address)
        self.manager_stub = parse_pb2_grpc.ParserManagerStub(
            self.manager_channel
        )

        await self.manager_channel.channel_ready()
        log.info(f"Connected to manager at {self.manager_address}")

        registration = parse_pb2.WorkerRegistration(
            worker_id=self.worker_id, host="localhost", port=self.port
        )
        log.info(f"Registering with manager: {registration}")
        response = await self.manager_stub.RegisterWorker(registration)
        log.info(f"Registration response: {response}")
        if response.success:
            log.info(f"Registered with manager: {response.message}")
            self._status_reporting_task = asyncio.create_task(
                self._report_status_periodically()
            )
        else:
            log.error(f"Failed to register with manager: {response.message}")

    async def _report_status_periodically(self):
        log.info(f"Starting status reporting for worker {self.worker_id}")
        while True:
            log.info(f"Reporting status for worker {self.worker_id}")
            try:
                status = (
                    parse_pb2.HealthCheckStatus.OK
                    if self.browser and self.browser.is_connected()
                    else parse_pb2.HealthCheckStatus.NOT_OK
                )
                log.info(f"Worker: {self.worker_id} Status: {status}")
                cpu_usage = psutil.cpu_percent(interval=0.1)
                memory_usage = psutil.virtual_memory().percent

                report = parse_pb2.StatusReport(
                    worker_id=self.worker_id,
                    port=self.port,
                    status=status,
                    active_pages=self._active_pages,
                    cpu_usage=cpu_usage,
                    memory_usage=memory_usage,
                )

                await self.manager_stub.ReportStatus(report)

            except Exception as e:
                log.error(f"Error reporting status: {e}")

            await asyncio.sleep(10)  # Report every 10 seconds

    async def _acquire_page(self):
        async with self._lock:
            if self._active_pages >= settings.browser.max_pages:
                raise RuntimeError("Maximum number of pages reached")
            self._active_pages += 1

    async def _release_page(self):
        async with self._lock:
            self._active_pages -= 1

    async def Parse(self, request, context):
        log.info("Acquiring page")
        page = None
        try:
            if self._shutdown_event.is_set():
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("Server is shutting down")
                return parse_pb2.ParseResponse()

            await self._acquire_page()
            if not self.browser:
                await self.init_browser()

            proxy = None
            if request.proxy:
                try:
                    creds, server = request.proxy.split("@")
                    username, password = creds.split(":")
                    proxy = {
                        "server": server,
                        "username": username,
                        "password": password,
                    }
                except ValueError as e:
                    raise ValueError("Invalid proxy format") from e

            log.info(
                f"Setting proxy: {proxy} and extra headers: {request.headers}"
            )
            page = await self.browser.new_page(
                proxy=proxy,
                extra_http_headers=request.headers,
            )

            log.info(f"Page created: {page}")

            if request.block:
                await page.route(
                    "**/*",
                    lambda route, req: asyncio.create_task(
                        route.abort()
                        if any(req.url.endswith(ext) for ext in request.block)
                        else route.continue_()
                    ),
                )

            log.info(f"Going to URL: {request.url}")
            response = await page.goto(
                request.url,
                timeout=request.timeout or settings.browser.timeout,
                wait_until=request.load or "networkidle",
            )

            if request.actions:
                for action in request.actions:
                    await self.execute_action(page, action)

            content = await page.content()
            headers = await response.all_headers() if response else {}
            cookies = [
                parse_pb2.Cookie(
                    name=c["name"],
                    value=c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", ""),
                    expires=int(c.get("expires", 0)),
                    http_only=c.get("httpOnly", False),
                    secure=c.get("secure", False),
                    same_site=c.get("sameSite", ""),
                )
                for c in await page.context.cookies()
            ]

            return parse_pb2.ParseResponse(
                status=response.status,
                content=content,
                error="",
                headers=headers,
                cookies=cookies,
            )

        except PlaywrightTimeoutError as e:
            log.error(f"TimeoutError: {e}")
            return parse_pb2.ParseResponse(
                status=418,
                content="",
                error=str(e),
                headers={},
                cookies=[],
            )
        except Exception as e:
            log.error(f"Exception: {e}")
            return parse_pb2.ParseResponse(
                status=518,
                content="",
                error=str(e),
                headers={},
                cookies=[],
            )
        finally:
            if page:
                await page.close()
            await self._release_page()

    async def execute_action(self, page: Page, action: parse_pb2.Action):
        if coro := getattr(page, action.func, None):
            log.info(
                f"Executing action {action.func} with arguments {action.args}"
            )
            await coro(
                **{
                    a.name: getattr(a, a.WhichOneof("value"), None)
                    for a in action.args
                }
            )
            log.info(f"Action {action.func} executed successfully")

    async def shutdown(self, server=None):
        log.info("Initiating graceful shutdown")
        self._shutdown_event.set()
        await server.stop(grace=5)
        await self.close_browser()

    async def serve(self):
        server = grpc.aio.server()
        parse_pb2_grpc.add_ParserWorkerServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{self.port}")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown(server))
            )

        await server.start()
        log.info(f"gRPC сервер запущен на порту {self.port}")

        try:
            await server.wait_for_termination()
        except asyncio.CancelledError:
            log.info("Server shutdown initiated")
        finally:
            await self.shutdown(server)
            await server.stop(grace=5)


def parse_args():
    parser = argparse.ArgumentParser(description="Parser Worker")
    parser.add_argument("--id", type=str, help="Worker ID")
    parser.add_argument("--port", type=int, default=50051, help="Worker port")
    parser.add_argument(
        "--manager",
        type=str,
        default=settings.server.manager_address,
        help="Manager address",
    )
    return parser.parse_args()


async def main():
    setup_logger()

    args = parse_args()

    worker = Worker(
        worker_id=args.id,
        manager_address=args.manager,
        port=args.port,
    )

    await worker.init_browser()
    await worker.connect_to_manager()
    await worker.serve()


if __name__ == "__main__":
    asyncio.run(main())
