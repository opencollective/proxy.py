# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Programmable Proxy Server in a single Python file.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import contextlib
import functools
import ipaddress
import socket

from types import TracebackType
from typing import Optional, Dict, Any, List, Tuple, Type, Callable
from typing_extensions import Literal

from .constants import HTTP_1_1, COLON, WHITESPACE, CRLF


def text_(s: Any, encoding: str = 'utf-8', errors: str = 'strict') -> Any:
    """Utility to ensure text-like usability.

    If s is of type bytes or int, return s.decode(encoding, errors),
    otherwise return s as it is."""
    if isinstance(s, int):
        return str(s)
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    return s


def bytes_(s: Any, encoding: str = 'utf-8', errors: str = 'strict') -> Any:
    """Utility to ensure binary-like usability.

    If s is type str or int, return s.encode(encoding, errors),
    otherwise return s as it is."""
    if isinstance(s, int):
        s = str(s)
    if isinstance(s, str):
        return s.encode(encoding, errors)
    return s


def build_http_request(method: bytes, url: bytes,
                       protocol_version: bytes = HTTP_1_1,
                       headers: Optional[Dict[bytes, bytes]] = None,
                       body: Optional[bytes] = None) -> bytes:
    """Build and returns a HTTP request packet."""
    if headers is None:
        headers = {}
    return build_http_pkt(
        [method, url, protocol_version], headers, body)


def build_http_response(status_code: int,
                        protocol_version: bytes = HTTP_1_1,
                        reason: Optional[bytes] = None,
                        headers: Optional[Dict[bytes, bytes]] = None,
                        body: Optional[bytes] = None) -> bytes:
    """Build and returns a HTTP response packet."""
    line = [protocol_version, bytes_(status_code)]
    if reason:
        line.append(reason)
    if headers is None:
        headers = {}
    has_content_length = False
    has_transfer_encoding = False
    for k in headers:
        if k.lower() == b'content-length':
            has_content_length = True
        if k.lower() == b'transfer-encoding':
            has_transfer_encoding = True
    if body is not None and \
            not has_transfer_encoding and \
            not has_content_length:
        headers[b'Content-Length'] = bytes_(len(body))
    return build_http_pkt(line, headers, body)


def build_http_header(k: bytes, v: bytes) -> bytes:
    """Build and return a HTTP header line for use in raw packet."""
    return k + COLON + WHITESPACE + v


def build_http_pkt(line: List[bytes],
                   headers: Optional[Dict[bytes, bytes]] = None,
                   body: Optional[bytes] = None) -> bytes:
    """Build and returns a HTTP request or response packet."""
    req = WHITESPACE.join(line) + CRLF
    if headers is not None:
        for k in headers:
            req += build_http_header(k, headers[k]) + CRLF
    req += CRLF
    if body:
        req += body
    return req


def build_websocket_handshake_request(
        key: bytes,
        method: bytes = b'GET',
        url: bytes = b'/') -> bytes:
    """
    Build and returns a Websocket handshake request packet.

    :param key: Sec-WebSocket-Key header value.
    :param method: HTTP method.
    :param url: Websocket request path.
    """
    return build_http_request(
        method, url,
        headers={
            b'Connection': b'upgrade',
            b'Upgrade': b'websocket',
            b'Sec-WebSocket-Key': key,
            b'Sec-WebSocket-Version': b'13',
        }
    )


def build_websocket_handshake_response(accept: bytes) -> bytes:
    """
    Build and returns a Websocket handshake response packet.

    :param accept: Sec-WebSocket-Accept header value
    """
    return build_http_response(
        101, reason=b'Switching Protocols',
        headers={
            b'Upgrade': b'websocket',
            b'Connection': b'Upgrade',
            b'Sec-WebSocket-Accept': accept
        }
    )


def find_http_line(raw: bytes) -> Tuple[Optional[bytes], bytes]:
    """Find and returns first line ending in CRLF along with following buffer.

    If no ending CRLF is found, line is None."""
    pos = raw.find(CRLF)
    if pos == -1:
        return None, raw
    line = raw[:pos]
    rest = raw[pos + len(CRLF):]
    return line, rest


def new_socket_connection(addr: Tuple[str, int]) -> socket.socket:
    conn = None
    try:
        ip = ipaddress.ip_address(addr[0])
        if ip.version == 4:
            conn = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM, 0)
            conn.connect(addr)
        else:
            conn = socket.socket(
                socket.AF_INET6, socket.SOCK_STREAM, 0)
            conn.connect((addr[0], addr[1], 0, 0))
    except ValueError:
        pass    # does not appear to be an IPv4 or IPv6 address

    if conn is not None:
        return conn

    # try to establish dual stack IPv4/IPv6 connection.
    return socket.create_connection(addr)


class socket_connection(contextlib.ContextDecorator):
    """Same as new_socket_connection but as a context manager and decorator."""

    def __init__(self, addr: Tuple[str, int]):
        self.addr: Tuple[str, int] = addr
        self.conn: Optional[socket.socket] = None
        super().__init__()

    def __enter__(self) -> socket.socket:
        self.conn = new_socket_connection(self.addr)
        return self.conn

    def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]) -> Literal[False]:
        if self.conn:
            self.conn.close()
        return False

    def __call__(self, func: Callable[..., Any]
                 ) -> Callable[[socket.socket], Any]:
        @functools.wraps(func)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            with self as conn:
                return func(conn, *args, **kwargs)
        return decorated
