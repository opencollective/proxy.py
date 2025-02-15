# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Programmable Proxy Server in a single Python file.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import socket
import ssl
import logging
from abc import ABC, abstractmethod
from typing import NamedTuple, Optional, Union, Tuple

from ..common.constants import DEFAULT_BUFFER_SIZE
from ..common.utils import new_socket_connection

logger = logging.getLogger(__name__)


TcpConnectionTypes = NamedTuple('TcpConnectionTypes', [
    ('SERVER', int),
    ('CLIENT', int),
])
tcpConnectionTypes = TcpConnectionTypes(1, 2)


class TcpConnectionUninitializedException(Exception):
    pass


class TcpConnection(ABC):
    """TCP server/client connection abstraction.

    Main motivation of this class is to provide a buffer management
    when reading and writing into the socket.

    Implement the connection property abstract method to return
    a socket connection object."""

    def __init__(self, tag: int):
        self.buffer: bytes = b''
        self.closed: bool = False
        self.tag: str = 'server' if tag == tcpConnectionTypes.SERVER else 'client'

    @property
    @abstractmethod
    def connection(self) -> Union[ssl.SSLSocket, socket.socket]:
        """Must return the socket connection to use in this class."""
        raise TcpConnectionUninitializedException()     # pragma: no cover

    def send(self, data: bytes) -> int:
        """Users must handle BrokenPipeError exceptions"""
        return self.connection.send(data)

    def recv(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> Optional[bytes]:
        """Users must handle socket.error exceptions"""
        data: bytes = self.connection.recv(buffer_size)
        if len(data) == 0:
            return None
        logger.debug(
            'received %d bytes from %s' %
            (len(data), self.tag))
        # logger.info(data)
        return data

    def close(self) -> bool:
        if not self.closed:
            self.connection.close()
            self.closed = True
        return self.closed

    def buffer_size(self) -> int:
        return len(self.buffer)

    def has_buffer(self) -> bool:
        return self.buffer_size() > 0

    def queue(self, data: bytes) -> int:
        self.buffer += data
        return len(data)

    def flush(self) -> int:
        """Users must handle BrokenPipeError exceptions"""
        if self.buffer_size() == 0:
            return 0
        sent: int = self.send(self.buffer)
        # logger.info(self.buffer[:sent])
        self.buffer = self.buffer[sent:]
        logger.debug('flushed %d bytes to %s' % (sent, self.tag))
        return sent


class TcpServerConnection(TcpConnection):
    """Establishes connection to upstream server."""

    def __init__(self, host: str, port: int):
        super().__init__(tcpConnectionTypes.SERVER)
        self._conn: Optional[Union[ssl.SSLSocket, socket.socket]] = None
        self.addr: Tuple[str, int] = (host, int(port))

    @property
    def connection(self) -> Union[ssl.SSLSocket, socket.socket]:
        if self._conn is None:
            raise TcpConnectionUninitializedException()
        return self._conn

    def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = new_socket_connection(self.addr)


class TcpClientConnection(TcpConnection):
    """An accepted client connection request."""

    def __init__(self,
                 conn: Union[ssl.SSLSocket, socket.socket],
                 addr: Tuple[str, int]):
        super().__init__(tcpConnectionTypes.CLIENT)
        self._conn: Optional[Union[ssl.SSLSocket, socket.socket]] = conn
        self.addr: Tuple[str, int] = addr

    @property
    def connection(self) -> Union[ssl.SSLSocket, socket.socket]:
        if self._conn is None:
            raise TcpConnectionUninitializedException()
        return self._conn
