"""
WebSocket performance benchmark suite for Django Channels.
"""

import asyncio
import json
import time
import psutil
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from django.core.management.base import BaseCommand
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
import logging

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Benchmark result container."""

    name: str
    concurrent_clients: int
    total_messages: int
    total_time: float
    avg_latency: float
    min_latency: float
    max_latency: float
    p95_latency: float
    p99_latency: float
    messages_per_second: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success_count: int
    failure_count: int
    errors: List[str] = field(default_factory=list)


class WebSocketBenchmark:
    """
    WebSocket performance benchmarking utility.
    """

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.channel_layer = get_channel_layer()

    async def benchmark_concurrent_clients(
        self,
        num_clients: int = 100,
        messages_per_client: int = 10,
        message_size: int = 1024,
    ) -> BenchmarkResult:
        """
        Benchmark concurrent WebSocket clients.

        Args:
            num_clients: Number of concurrent clients
            messages_per_client: Messages to send per client
            message_size: Size of each message in bytes
        """
        start_time = time.time()
        success_count = 0
        failure_count = 0
        errors = []
        latencies = []

        async def client_task(client_id: int):
            nonlocal success_count, failure_count, errors
            try:
                communicator = WebsocketCommunicator(
                    self.get_application(), f"/ws/test/benchmark/?client_id={client_id}"
                )
                connected, _ = await communicator.connect()

                if not connected:
                    failure_count += 1
                    errors.append(f"Client {client_id} failed to connect")
                    return

                for i in range(messages_per_client):
                    msg_start = time.time()
                    await communicator.send_to(
                        json.dumps(
                            {
                                "type": "benchmark",
                                "client_id": client_id,
                                "sequence": i,
                                "data": "x" * message_size,
                            }
                        )
                    )

                    response = await communicator.receive_from()
                    msg_end = time.time()
                    latency = (msg_end - msg_start) * 1000  # in milliseconds
                    latencies.append(latency)

                await communicator.disconnect()
                success_count += 1

            except Exception as e:
                failure_count += 1
                errors.append(f"Client {client_id} error: {str(e)}")

        # Run clients concurrently
        tasks = [client_task(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Calculate statistics
        total_messages = success_count * messages_per_client
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0

        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p99_index = int(len(sorted_latencies) * 0.99)
        p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0
        p99_latency = sorted_latencies[p99_index] if sorted_latencies else 0

        # Memory and CPU usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)

        result = BenchmarkResult(
            name="concurrent_clients",
            concurrent_clients=num_clients,
            total_messages=total_messages,
            total_time=total_time,
            avg_latency=avg_latency,
            min_latency=min_latency,
            max_latency=max_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            messages_per_second=total_messages / total_time if total_time > 0 else 0,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
        )

        self.results.append(result)
        return result

    async def benchmark_broadcast_latency(
        self, num_clients: int = 50, broadcasts: int = 10
    ) -> BenchmarkResult:
        """
        Benchmark broadcast latency.

        Args:
            num_clients: Number of clients to broadcast to
            broadcasts: Number of broadcast messages
        """
        start_time = time.time()
        success_count = 0
        failure_count = 0
        errors = []
        latencies = []

        # Create clients
        clients = []
        for i in range(num_clients):
            communicator = WebsocketCommunicator(
                self.get_application(), f"/ws/test/benchmark/?client_id={i}"
            )
            connected, _ = await communicator.connect()
            if connected:
                clients.append(communicator)
                success_count += 1
            else:
                failure_count += 1
                errors.append(f"Client {i} failed to connect")

        if not clients:
            return self._create_empty_result("broadcast_latency")

        for _ in range(broadcasts):
            broadcast_start = time.time()

            # Send broadcast message
            await self.channel_layer.group_send(
                "benchmark_group",
                {"type": "benchmark_message", "data": {"timestamp": broadcast_start}},
            )

            # Wait for responses
            for client in clients:
                try:
                    response = await client.receive_from()
                    latency = (time.time() - broadcast_start) * 1000
                    latencies.append(latency)
                except Exception as e:
                    errors.append(str(e))

        # Cleanup
        for client in clients:
            await client.disconnect()

        total_time = time.time() - start_time
        total_messages = len(latencies)

        result = BenchmarkResult(
            name="broadcast_latency",
            concurrent_clients=num_clients,
            total_messages=total_messages,
            total_time=total_time,
            avg_latency=sum(latencies) / len(latencies) if latencies else 0,
            min_latency=min(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            p95_latency=0,
            p99_latency=0,
            messages_per_second=total_messages / total_time if total_time > 0 else 0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
        )

        self.results.append(result)
        return result

    async def benchmark_reconnect_performance(
        self, num_reconnects: int = 100
    ) -> BenchmarkResult:
        """
        Benchmark reconnect performance.

        Args:
            num_reconnects: Number of reconnect attempts
        """
        start_time = time.time()
        success_count = 0
        failure_count = 0
        errors = []
        reconnect_times = []

        for i in range(num_reconnects):
            try:
                connect_start = time.time()
                communicator = WebsocketCommunicator(
                    self.get_application(), f"/ws/test/benchmark/?client_id={i}"
                )
                connected, _ = await communicator.connect()

                if connected:
                    reconnect_time = (time.time() - connect_start) * 1000
                    reconnect_times.append(reconnect_time)
                    await communicator.disconnect()
                    success_count += 1
                else:
                    failure_count += 1
                    errors.append(f"Reconnect {i} failed")

            except Exception as e:
                failure_count += 1
                errors.append(f"Reconnect {i} error: {str(e)}")

        total_time = time.time() - start_time

        result = BenchmarkResult(
            name="reconnect_performance",
            concurrent_clients=num_reconnects,
            total_messages=num_reconnects,
            total_time=total_time,
            avg_latency=(
                sum(reconnect_times) / len(reconnect_times) if reconnect_times else 0
            ),
            min_latency=min(reconnect_times) if reconnect_times else 0,
            max_latency=max(reconnect_times) if reconnect_times else 0,
            p95_latency=0,
            p99_latency=0,
            messages_per_second=num_reconnects / total_time if total_time > 0 else 0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
        )

        self.results.append(result)
        return result

    def get_application(self):
        """Get the ASGI application."""
        from django.core.asgi import get_asgi_application
        from channels.routing import ProtocolTypeRouter, URLRouter
        from django.urls import path
        from apps.benchmark.consumers import BenchmarkConsumer

        return ProtocolTypeRouter(
            {
                "websocket": URLRouter(
                    [
                        path("ws/test/benchmark/", BenchmarkConsumer.as_asgi()),
                    ]
                )
            }
        )

    def _create_empty_result(self, name: str) -> BenchmarkResult:
        """Create an empty result for failed benchmarks."""
        return BenchmarkResult(
            name=name,
            concurrent_clients=0,
            total_messages=0,
            total_time=0,
            avg_latency=0,
            min_latency=0,
            max_latency=0,
            p95_latency=0,
            p99_latency=0,
            messages_per_second=0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            success_count=0,
            failure_count=0,
            errors=["Benchmark failed"],
        )

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive benchmark report."""
        report = {"timestamp": time.time(), "results": []}

        for result in self.results:
            report["results"].append(
                {
                    "name": result.name,
                    "concurrent_clients": result.concurrent_clients,
                    "total_messages": result.total_messages,
                    "total_time_seconds": round(result.total_time, 2),
                    "avg_latency_ms": round(result.avg_latency, 2),
                    "min_latency_ms": round(result.min_latency, 2),
                    "max_latency_ms": round(result.max_latency, 2),
                    "p95_latency_ms": round(result.p95_latency, 2),
                    "p99_latency_ms": round(result.p99_latency, 2),
                    "messages_per_second": round(result.messages_per_second, 2),
                    "memory_usage_mb": round(result.memory_usage_mb, 2),
                    "cpu_usage_percent": round(result.cpu_usage_percent, 2),
                    "success_rate": round(
                        (
                            (
                                result.success_count
                                / (result.success_count + result.failure_count)
                            )
                            * 100
                            if (result.success_count + result.failure_count) > 0
                            else 0
                        ),
                        2,
                    ),
                    "errors": result.errors[:10],  # Show first 10 errors
                }
            )

        return report

    def generate_markdown_report(self) -> str:
        """Generate a markdown report."""
        report = self.generate_report()

        lines = [
            "# 🔌 WebSocket Performance Benchmark Report",
            "",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]

        if report["results"]:
            for result in report["results"]:
                lines.append(f"| **{result['name']}** | |")
                lines.append(
                    f"| - Concurrent Clients | {result['concurrent_clients']} |"
                )
                lines.append(f"| - Total Messages | {result['total_messages']} |")
                lines.append(f"| - Avg Latency | {result['avg_latency_ms']}ms |")
                lines.append(f"| - P95 Latency | {result['p95_latency_ms']}ms |")
                lines.append(f"| - P99 Latency | {result['p99_latency_ms']}ms |")
                lines.append(f"| - Messages/sec | {result['messages_per_second']} |")
                lines.append(f"| - Success Rate | {result['success_rate']}% |")
                lines.append("")

        return "\n".join(lines)
