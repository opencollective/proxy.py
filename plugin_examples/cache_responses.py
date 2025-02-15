# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Programmable, TLS interception capable
    proxy server for Application debugging, testing and development.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import os
import tempfile
import time
import logging
from typing import Optional, BinaryIO

from proxy.common.flags import Flags
from proxy.core.connection import TcpClientConnection
from proxy.http.parser import HttpParser
from proxy.http.proxy import HttpProxyBasePlugin
from proxy.common.utils import text_

logger = logging.getLogger(__name__)


class CacheResponsesPlugin(HttpProxyBasePlugin):
    """Caches Upstream Server Responses."""

    CACHE_DIR = tempfile.gettempdir()

    def __init__(
            self,
            config: Flags,
            client: TcpClientConnection) -> None:
        super().__init__(config, client)
        self.cache_file_path: Optional[str] = None
        self.cache_file: Optional[BinaryIO] = None

    def before_upstream_connection(
            self, request: HttpParser) -> Optional[HttpParser]:
        # Ideally should only create file if upstream connection succeeds.
        self.cache_file_path = os.path.join(
            self.CACHE_DIR,
            '%s-%s.txt' % (text_(request.host), str(time.time())))
        self.cache_file = open(self.cache_file_path, "wb")
        return request

    def handle_client_request(
            self, request: HttpParser) -> Optional[HttpParser]:
        return request

    def handle_upstream_chunk(self,
                              chunk: bytes) -> bytes:
        if self.cache_file:
            self.cache_file.write(chunk)
        return chunk

    def on_upstream_connection_close(self) -> None:
        if self.cache_file:
            self.cache_file.close()
        logger.info('Cached response at %s', self.cache_file_path)
