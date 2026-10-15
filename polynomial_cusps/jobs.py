"""One cancellable background worker; obsolete results never become current."""

from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Event

from .rendering import RenderCancelled


class BackgroundJobs:
    def __init__(self):
        self.generation = 0
        self._event = Event()
        self._queue = Queue()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cusps-render")

    def submit(self, work):
        self.cancel()
        generation, cancel = self.generation, self._event

        def run():
            if cancel.is_set():
                return
            try:
                value = work(cancel, lambda p: self._queue.put((generation, "progress", p)))
                if not cancel.is_set():
                    self._queue.put((generation, "result", value))
            except RenderCancelled:
                pass
            except Exception as error:
                if not cancel.is_set():
                    self._queue.put((generation, "error", error))
        self._executor.submit(run)
        return generation

    def cancel(self):
        self._event.set()
        self.generation += 1
        self._event = Event()

    def poll(self):
        messages = []
        while True:
            try:
                generation, kind, value = self._queue.get_nowait()
            except Empty:
                return messages
            if generation == self.generation:
                messages.append((kind, value))

    def close(self):
        self.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
