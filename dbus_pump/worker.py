"""Serialize bounded HA work without blocking the D-Bus main loop."""

import logging
import queue
import threading
import time

logger = logging.getLogger("dbus-pump")


class HaWorker:
    """One network worker; dispatch all completion callbacks to the main loop."""

    def __init__(self, client, dispatch, shutdown_entity, queue_size=8, clock=time.monotonic):
        self.client = client
        self.dispatch = dispatch
        self.shutdown_entity = shutdown_entity
        self._clock = clock
        self._queue = queue.Queue(maxsize=queue_size)
        self._stopping = threading.Event()
        # Only the main loop reads/writes _poll_pending.
        self._poll_pending = False
        self._commands = {}
        self._thread = threading.Thread(target=self._run, name="ha-worker", daemon=True)
        self._thread.start()

    def poll(self, callback):
        if self._poll_pending or self._stopping.is_set():
            return False
        self._poll_pending = self._submit("poll", (), callback)
        return self._poll_pending

    def call_service(self, domain, action, entity, callback):
        cancelled = threading.Event()
        if not self._submit("service", (domain, action, entity), callback, cancelled):
            return False
        self.cancel_service(entity)
        self._commands[entity] = (action, cancelled)
        return True

    def cancel_service(self, entity):
        previous = self._commands.pop(entity, None)
        if previous is not None:
            previous[1].set()

    def service_pending(self, entity, action):
        previous = self._commands.get(entity)
        return previous is not None and previous[0] == action and not previous[1].is_set()

    def _submit(self, kind, args, callback, cancelled=None):
        if self._stopping.is_set():
            return False
        try:
            self._queue.put_nowait((kind, args, callback, cancelled))
        except queue.Full:
            logger.warning("HA work queue full; request deferred or rejected")
            return False
        return True

    def _deliver(self, kind, args, callback, result, failed, cancelled):
        if kind == "poll":
            self._poll_pending = False
        elif self._commands.get(args[2], (None, None))[1] is cancelled:
            self._commands.pop(args[2])
        if (
            not self._stopping.is_set()
            and (cancelled is None or not cancelled.is_set())
            and (not failed or kind == "service")
        ):
            callback(False if failed else result)
        return False  # GLib idle callbacks must run only once.

    def _run(self):
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    break
                kind, args, callback, cancelled = item
                if self._stopping.is_set() or (cancelled is not None and cancelled.is_set()):
                    continue
                failed = False
                result = None
                try:
                    started_at = self._clock()
                    result = (
                        self.client.poll() if kind == "poll" else self.client.call_service(*args)
                    )
                    if kind == "poll":
                        result = dict(result, _sample_started_at=started_at)
                except Exception:
                    failed = True
                    logger.exception("HA worker request failed")
                self.dispatch(self._deliver, kind, args, callback, result, failed, cancelled)
        finally:
            # Close only after the in-flight request; never race a Session or
            # allow queued ON commands to run after the shutdown OFF request.
            try:
                if self.client.call_service("switch", "turn_off", self.shutdown_entity):
                    logger.info("Shutdown: valve forced closed")
            except Exception:
                logger.exception("Shutdown: failed to close valve")
            self.client.close()

    def stop(self, timeout=15.0):
        """Cancel queued work, finish the active request, and close the valve."""
        if not self._stopping.is_set():
            self._stopping.set()
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._queue.put_nowait(None)
        self._thread.join(timeout)
        if self._thread.is_alive():
            logger.error("HA worker shutdown deadline expired; valve closure is unconfirmed")
            return False
        return True
