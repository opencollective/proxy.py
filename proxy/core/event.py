# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Programmable Proxy Server in a single Python file.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import os
import queue
import time
import threading
import multiprocessing
import logging

from typing import Dict, Optional, Any, NamedTuple, List

from ..common.types import DictQueueType

logger = logging.getLogger(__name__)


EventNames = NamedTuple('EventNames', [
    ('WORK_STARTED', int),
    ('WORK_FINISHED', int),
    ('SUBSCRIBE', int),
    ('UNSUBSCRIBE', int),
])
eventNames = EventNames(1, 2, 3, 4)


class EventQueue:
    """Global event queue."""

    def __init__(self) -> None:
        super().__init__()
        self.queue = multiprocessing.Manager().Queue()

    def publish(
        self,
        request_id: str,
        event_name: int,
        event_payload: Dict[str, Any],
        publisher_id: Optional[str] = None
    ) -> None:
        """Publish an event into the queue.

        1. Request ID               - Globally unique
        2. Process ID               - Process ID of event publisher.
                                      This will be process id of acceptor workers.
        3. Thread ID                - Thread ID of event publisher.
                                      When --threadless is enabled, this value will be same for all the requests
                                      received by a single acceptor worker.
                                      When --threadless is disabled, this value will be
                                      Thread ID of the thread handling the client request.
        4. Event Timestamp          - Time when this event occur
        5. Event Name               - One of the defined or custom event name
        6. Event Payload            - Optional data associated with the event
        7. Publisher ID (optional)  - Optionally, publishing entity unique name / ID
        """
        self.queue.put({
            'request_id': request_id,
            'process_id': os.getpid(),
            'thread_id': threading.get_ident(),
            'event_timestamp': time.time(),
            'event_name': event_name,
            'event_payload': event_payload,
            'publisher_id': publisher_id,
        })

    def subscribe(
            self,
            sub_id: str,
            channel: DictQueueType) -> None:
        self.queue.put({
            'event_name': eventNames.SUBSCRIBE,
            'event_payload': {'sub_id': sub_id, 'channel': channel},
        })


class EventDispatcher:
    """Core EventDispatcher.

    Provides:
    1. A dispatcher module which consumes core events and dispatches
       them to EventQueueBasePlugin
    2. A publish utility for publishing core events into
       global events queue.

    Direct consuming from global events queue outside of dispatcher
    module is not-recommended.  Python native multiprocessing queue
    doesn't provide a fanout functionality which core dispatcher module
    implements so that several plugins can consume same published
    event at a time.

    When --enable-events is used, a multiprocessing.Queue is created and
    attached to global Flags.  This queue can then be used for
    dispatching an Event dict object into the queue.

    When --enable-events is used, dispatcher module is automatically
    started. Dispatcher module also ensures that queue is not full and
    doesn't utilize too much memory in case there are no event plugins
    enabled.
    """

    def __init__(
            self,
            shutdown: threading.Event,
            event_queue: EventQueue) -> None:
        self.shutdown: threading.Event = shutdown
        self.event_queue: EventQueue = event_queue
        self.subscribers: Dict[str, DictQueueType] = {}

    def run(self) -> None:
        try:
            while not self.shutdown.is_set():
                try:
                    ev = self.event_queue.queue.get(timeout=1)
                    if ev['event_name'] == eventNames.SUBSCRIBE:
                        self.subscribers[ev['event_payload']['sub_id']] = \
                            ev['event_payload']['channel']
                    elif ev['event_name'] == eventNames.UNSUBSCRIBE:
                        del self.subscribers[ev['event_payload']['sub_id']]
                    else:
                        # logger.info(ev)
                        unsub_ids: List[str] = []
                        for sub_id in self.subscribers:
                            try:
                                self.subscribers[sub_id].put(ev)
                            except BrokenPipeError:
                                unsub_ids.append(sub_id)
                        for sub_id in unsub_ids:
                            del self.subscribers[sub_id]
                except queue.Empty:
                    pass
        except EOFError:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.exception('Event dispatcher exception', exc_info=e)
