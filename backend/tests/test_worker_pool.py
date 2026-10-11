"""The bounded provider path must use stable public concurrency primitives."""

import ast
import inspect
from concurrent.futures import ThreadPoolExecutor

from app import service


def test_provider_pool_is_fixed_and_uses_no_cpython_private_executor_api() -> None:
    source = inspect.getsource(service)
    tree = ast.parse(source)
    forbidden = ("_worker", "_threads_queues", "_initializer", "_initargs", "_DaemonThreadPoolExecutor")
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not referenced_names.intersection(forbidden)
    assert isinstance(service._provider_pool, ThreadPoolExecutor)
    assert service.MAX_CONCURRENT_PROVIDER_WORK > 0
