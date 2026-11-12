import inspect
import time
import threading
from collections import defaultdict
from functools import wraps
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphInterrupt


class AgentMonitor:
    def __init__(self):
        self.events = defaultdict(list)
        self.lock = threading.Lock()

    def record(self, thread_id, node, status, duration, details=None):
        event = {
            "timestamp": time.time(),
            "node": node,
            "status": status,
            "duration": round(duration, 4),
            "details": details or {},
        }

        with self.lock:
            self.events[thread_id].append(event)

    def get_events(self, thread_id):
        with self.lock:
            return list(self.events.get(thread_id, []))

    def clear(self, thread_id):
        with self.lock:
            self.events.pop(thread_id, None)


monitor = AgentMonitor()


def trace_node(name, function):
    parameters = inspect.signature(
        function, follow_wrapped=False
    ).parameters

    accepts_config = "config" in parameters

    # Burada @wraps kullanmıyoruz.
    # LangGraph wrapper'ın gerçek imzasını görmeli.
    def wrapper(state, config: RunnableConfig):
        start = time.perf_counter()

        thread_id = config.get(
            "configurable", {}
        ).get("thread_id", "unknown")

        print(
            f"[TRACE] {name} başladı "
            f"(thread={thread_id})",
            flush=True
        )

        try:
            if accepts_config:
                result = function(state, config=config)
            else:
                result = function(state)

            duration = time.perf_counter() - start

            monitor.record(
                thread_id=thread_id,
                node=name,
                status="success",
                duration=duration,
                details={
                    "attempts": state.get("attempts", 0)
                }
            )

            print(
                f"[TRACE] {name} başarılı "
                f"({duration:.3f} sn)",
                flush=True
            )

            return result
        

        except GraphInterrupt:
            duration = time.perf_counter() - start

            monitor.record(
                thread_id=thread_id,
                node=name,
                status="interrupted",
                duration=duration,
                details={
                    "reason": "Waiting for user approval"
                }
            )

            print(
                f"[TRACE] {name} kullanıcı onayı bekliyor "
                f"({duration:.3f} sn)",
                flush=True
            )

            raise


        except Exception as e:
            duration = time.perf_counter() - start

            monitor.record(
                thread_id=thread_id,
                node=name,
                status="error",
                duration=duration,
                details={"error": str(e)}
            )

            print(
                f"[TRACE] {name} başarısız "
                f"({duration:.3f} sn)",
                flush=True
            )

            raise

    return wrapper