import queue
import threading
from collections import defaultdict
from typing import Dict, List

# Map of thread_id -> list of queue.Queue
terminal_streams: Dict[str, List[queue.Queue]] = defaultdict(list)
lock = threading.Lock()

def add_queue(thread_id: str) -> queue.Queue:
    q = queue.Queue()
    with lock:
        terminal_streams[thread_id].append(q)
    return q

def remove_queue(thread_id: str, q: queue.Queue):
    with lock:
        if thread_id in terminal_streams and q in terminal_streams[thread_id]:
            terminal_streams[thread_id].remove(q)
            if not terminal_streams[thread_id]:
                del terminal_streams[thread_id]

def publish(thread_id: str, message: str):
    with lock:
        qs = terminal_streams.get(thread_id, [])
        for q in qs:
            q.put(message)
