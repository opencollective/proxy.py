
class TestHttpProxyPluginExamples(unittest.TestCase):

    @mock.patch('selectors.DefaultSelector')
    @mock.patch('socket.fromfd')
    def setUp(self,
              mock_fromfd: mock.Mock,
              mock_selector: mock.Mock) -> None:
        self.fileno = 10
        self._addr = ('127.0.0.1', 54382)
        self.flags = proxy.Flags()
        self.plugin = mock.MagicMock()

        self.mock_fromfd = mock_fromfd
        self.mock_selector = mock_selector

        plugin = get_plugin_by_test_name(self._testMethodName)

        self.flags.plugins = {
            b'ProtocolHandlerPlugin': [proxy.HttpProxyPlugin],
            b'HttpProxyBasePlugin': [plugin],
        }
        self._conn = mock_fromfd.return_value
        self.proxy = proxy.ProtocolHandler(
            self.fileno, self._addr, flags=self.flags)
        self.proxy.initialize()

    @mock.patch('proxy.TcpServerConnection')
    def test_modify_post_data_plugin(self, mock_server_conn: mock.Mock) -> None:
        original = b'{"key": "value"}'
        modified = b'{"key": "modified"}'

        self._conn.recv.return_value = proxy.build_http_request(
            b'POST', b'http://httpbin.org/post',
            headers={
                b'Host': b'httpbin.org',
                b'Content-Type': b'application/x-www-form-urlencoded',
                b'Content-Length': proxy.bytes_(len(original)),
            },
            body=original
        )
        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]

        self.proxy.run_once()
        mock_server_conn.assert_called_with('httpbin.org', 80)
        mock_server_conn.return_value.queue.assert_called_with(
            proxy.build_http_request(
                b'POST', b'/post',
                headers={
                    b'Host': b'httpbin.org',
                    b'Content-Length': proxy.bytes_(len(modified)),
                    b'Content-Type': b'application/json',
                    b'Via': b'1.1 %s' % proxy.PROXY_AGENT_HEADER_VALUE,
                },
                body=modified
            )
        )

    @mock.patch('proxy.TcpServerConnection')
    def test_proposed_rest_api_plugin(
            self, mock_server_conn: mock.Mock) -> None:
        path = b'/v1/users/'
        self._conn.recv.return_value = proxy.build_http_request(
            b'GET', b'http://%s%s' % (plugin_examples.ProposedRestApiPlugin.API_SERVER, path),
            headers={
                b'Host': plugin_examples.ProposedRestApiPlugin.API_SERVER,
            }
        )
        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]
        self.proxy.run_once()

        mock_server_conn.assert_not_called()
        self.assertEqual(
            self.proxy.client.buffer,
            proxy.build_http_response(
                proxy.httpStatusCodes.OK, reason=b'OK',
                headers={b'Content-Type': b'application/json'},
                body=proxy.bytes_(json.dumps(plugin_examples.ProposedRestApiPlugin.REST_API_SPEC[path]))
            ))

    @mock.patch('proxy.TcpServerConnection')
    def test_redirect_to_custom_server_plugin(
            self, mock_server_conn: mock.Mock) -> None:
        request = proxy.build_http_request(
            b'GET', b'http://example.org/get',
            headers={
                b'Host': b'example.org',
            }
        )
        self._conn.recv.return_value = request
        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]
        self.proxy.run_once()

        upstream = urlparse.urlsplit(
            plugin_examples.RedirectToCustomServerPlugin.UPSTREAM_SERVER)
        mock_server_conn.assert_called_with('localhost', 8899)
        mock_server_conn.return_value.queue.assert_called_with(
            proxy.build_http_request(
                b'GET', upstream.path,
                headers={
                    b'Host': upstream.netloc,
                    b'Via': b'1.1 %s' % proxy.PROXY_AGENT_HEADER_VALUE,
                }
            )
        )

    @mock.patch('proxy.TcpServerConnection')
    def test_filter_by_upstream_host_plugin(
            self, mock_server_conn: mock.Mock) -> None:
        request = proxy.build_http_request(
            b'GET', b'http://google.com/',
            headers={
                b'Host': b'google.com',
            }
        )
        self._conn.recv.return_value = request
        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]
        self.proxy.run_once()

        mock_server_conn.assert_not_called()
        self.assertEqual(
            self.proxy.client.buffer,
            proxy.build_http_response(
                proxy.httpStatusCodes.I_AM_A_TEAPOT,
                reason=b'I\'m a tea pot',
                headers={
                    proxy.PROXY_AGENT_HEADER_KEY: proxy.PROXY_AGENT_HEADER_VALUE
                },
            )
        )

    @mock.patch('proxy.TcpServerConnection')
    def test_man_in_the_middle_plugin(
            self, mock_server_conn: mock.Mock) -> None:
        request = proxy.build_http_request(
            b'GET', b'http://super.secure/',
            headers={
                b'Host': b'super.secure',
            }
        )
        self._conn.recv.return_value = request

        server = mock_server_conn.return_value
        server.connect.return_value = True

        def has_buffer() -> bool:
            return cast(bool, server.queue.called)

        def closed() -> bool:
            return not server.connect.called

        server.has_buffer.side_effect = has_buffer
        type(server).closed = mock.PropertyMock(side_effect=closed)

        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)],
            [(selectors.SelectorKey(
                fileobj=server.connection,
                fd=server.connection.fileno,
                events=selectors.EVENT_WRITE,
                data=None), selectors.EVENT_WRITE)],
            [(selectors.SelectorKey(
                fileobj=server.connection,
                fd=server.connection.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]

        # Client read
        self.proxy.run_once()
        mock_server_conn.assert_called_with('super.secure', 80)
        server.connect.assert_called_once()
        queued_request = \
            proxy.build_http_request(
                b'GET', b'/',
                headers={
                    b'Host': b'super.secure',
                    b'Via': b'1.1 %s' % proxy.PROXY_AGENT_HEADER_VALUE
                }
            )
        server.queue.assert_called_once_with(queued_request)

        # Server write
        self.proxy.run_once()
        server.flush.assert_called_once()

        # Server read
        server.recv.return_value = \
            proxy.build_http_response(
                proxy.httpStatusCodes.OK,
                reason=b'OK', body=b'Original Response From Upstream')
        self.proxy.run_once()
        self.assertEqual(
            self.proxy.client.buffer,
            proxy.build_http_response(
                proxy.httpStatusCodes.OK,
                reason=b'OK', body=b'Hello from man in the middle')
        )


class TestHttpProxyPluginExamplesWithTlsInterception(unittest.TestCase):

    @mock.patch('ssl.wrap_socket')
    @mock.patch('ssl.create_default_context')
    @mock.patch('proxy.TcpServerConnection')
    @mock.patch('subprocess.Popen')
    @mock.patch('selectors.DefaultSelector')
    @mock.patch('socket.fromfd')
    def setUp(self,
              mock_fromfd: mock.Mock,
              mock_selector: mock.Mock,
              mock_popen: mock.Mock,
              mock_server_conn: mock.Mock,
              mock_ssl_context: mock.Mock,
              mock_ssl_wrap: mock.Mock) -> None:
        self.mock_fromfd = mock_fromfd
        self.mock_selector = mock_selector
        self.mock_popen = mock_popen
        self.mock_server_conn = mock_server_conn
        self.mock_ssl_context = mock_ssl_context
        self.mock_ssl_wrap = mock_ssl_wrap

        self.fileno = 10
        self._addr = ('127.0.0.1', 54382)
        self.flags = proxy.Flags(
            ca_cert_file='ca-cert.pem',
            ca_key_file='ca-key.pem',
            ca_signing_key_file='ca-signing-key.pem',)
        self.plugin = mock.MagicMock()

        plugin = get_plugin_by_test_name(self._testMethodName)

        self.flags.plugins = {
            b'ProtocolHandlerPlugin': [proxy.HttpProxyPlugin],
            b'HttpProxyBasePlugin': [plugin],
        }
        self._conn = mock.MagicMock(spec=socket.socket)
        mock_fromfd.return_value = self._conn
        self.proxy = proxy.ProtocolHandler(
            self.fileno, self._addr, flags=self.flags)
        self.proxy.initialize()

        self.server = self.mock_server_conn.return_value

        self.server_ssl_connection = mock.MagicMock(spec=ssl.SSLSocket)
        self.mock_ssl_context.return_value.wrap_socket.return_value = self.server_ssl_connection
        self.client_ssl_connection = mock.MagicMock(spec=ssl.SSLSocket)
        self.mock_ssl_wrap.return_value = self.client_ssl_connection

        def has_buffer() -> bool:
            return cast(bool, self.server.queue.called)

        def closed() -> bool:
            return not self.server.connect.called

        def mock_connection() -> Any:
            if self.mock_ssl_context.return_value.wrap_socket.called:
                return self.server_ssl_connection
            return self._conn

        self.server.has_buffer.side_effect = has_buffer
        type(self.server).closed = mock.PropertyMock(side_effect=closed)
        type(self.server).connection = mock.PropertyMock(side_effect=mock_connection)

        self.mock_selector.return_value.select.side_effect = [
            [(selectors.SelectorKey(
                fileobj=self._conn,
                fd=self._conn.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)],
            [(selectors.SelectorKey(
                fileobj=self.client_ssl_connection,
                fd=self.client_ssl_connection.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)],
            [(selectors.SelectorKey(
                fileobj=self.server_ssl_connection,
                fd=self.server_ssl_connection.fileno,
                events=selectors.EVENT_WRITE,
                data=None), selectors.EVENT_WRITE)],
            [(selectors.SelectorKey(
                fileobj=self.server_ssl_connection,
                fd=self.server_ssl_connection.fileno,
                events=selectors.EVENT_READ,
                data=None), selectors.EVENT_READ)], ]

        # Connect
        def send(raw: bytes) -> int:
            return len(raw)

        self._conn.send.side_effect = send
        self._conn.recv.return_value = proxy.build_http_request(
            proxy.httpMethods.CONNECT, b'uni.corn:443'
        )
        self.proxy.run_once()

        self.mock_popen.assert_called()
        self.mock_server_conn.assert_called_once_with('uni.corn', 443)
        self.server.connect.assert_called()
        self.assertEqual(self.proxy.client.connection, self.client_ssl_connection)
        self.assertEqual(self.server.connection, self.server_ssl_connection)
        self._conn.send.assert_called_with(
            proxy.HttpProxyPlugin.PROXY_TUNNEL_ESTABLISHED_RESPONSE_PKT
        )
        self.assertEqual(self.proxy.client.buffer, b'')

    def test_modify_post_data_plugin(self) -> None:
        original = b'{"key": "value"}'
        modified = b'{"key": "modified"}'
        self.client_ssl_connection.recv.return_value = proxy.build_http_request(
            b'POST', b'/',
            headers={
                b'Host': b'uni.corn',
                b'Content-Type': b'application/x-www-form-urlencoded',
                b'Content-Length': proxy.bytes_(len(original)),
            },
            body=original
        )
        self.proxy.run_once()
        self.server.queue.assert_called_with(
            proxy.build_http_request(
                b'POST', b'/',
                headers={
                    b'Host': b'uni.corn',
                    b'Content-Length': proxy.bytes_(len(modified)),
                    b'Content-Type': b'application/json',
                },
                body=modified
            )
        )

    @mock.patch('proxy.TcpServerConnection')
    def test_man_in_the_middle_plugin(
            self, mock_server_conn: mock.Mock) -> None:
        request = proxy.build_http_request(
            b'GET', b'/',
            headers={
                b'Host': b'uni.corn',
            }
        )
        self.client_ssl_connection.recv.return_value = request

        # Client read
        self.proxy.run_once()
        self.server.queue.assert_called_once_with(request)

        # Server write
        self.proxy.run_once()
        self.server.flush.assert_called_once()

        # Server read
        self.server.recv.return_value = \
            proxy.build_http_response(
                proxy.httpStatusCodes.OK,
                reason=b'OK', body=b'Original Response From Upstream')
        self.proxy.run_once()
        self.assertEqual(
            self.proxy.client.buffer,
            proxy.build_http_response(
                proxy.httpStatusCodes.OK,
                reason=b'OK', body=b'Hello from man in the middle')
        )
