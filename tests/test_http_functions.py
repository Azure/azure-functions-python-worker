from azure.functions_worker import testutils


class TestHttpFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'http_functions'

    def test_return_str(self):
        r = self.webhost.request('GET', 'return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))

    def test_return_out(self):
        r = self.webhost.request('GET', 'return_out')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.text, 'hello')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))

    def test_return_bytes(self):
        r = self.webhost.request('GET', 'return_bytes')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertRegex(
        #    r.text, r'.*unsupported type .*http.* for Python type .*bytes.*')

    def test_return_http_200(self):
        r = self.webhost.request('GET', 'return_http')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.headers['content-type'], 'text/html; charset=utf-8')

    def test_return_http_auth_level_admin(self):
        r = self.webhost.request('GET', 'return_http_auth_admin',
                                 params={'code': 'testMasterKey'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.headers['content-type'], 'text/html; charset=utf-8')

    def test_return_http_404(self):
        r = self.webhost.request('GET', 'return_http_404')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.text, 'bye')
        self.assertEqual(r.headers['content-type'],
                         'text/plain; charset=utf-8')

    def test_return_http_redirect(self):
        r = self.webhost.request('GET', 'return_http_redirect')
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.status_code, 200)

        r = self.webhost.request('GET', 'return_http_redirect',
                                 allow_redirects=False)
        self.assertEqual(r.status_code, 302)

    def test_no_return(self):
        r = self.webhost.request('GET', 'no_return')
        self.assertEqual(r.status_code, 204)

    def test_no_return_returns(self):
        r = self.webhost.request('GET', 'no_return_returns')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertRegex(r.text,
        #                  r'.*function .+no_return_returns.+ without a '
        #                  r'\$return binding returned a non-None value.*')

    def test_async_return_str(self):
        r = self.webhost.request('GET', 'async_return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello Async World!')

    def test_async_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'async_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-async')

    def test_sync_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'sync_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-sync')

    def test_return_context(self):
        r = self.webhost.request('GET', 'return_context')
        self.assertEqual(r.status_code, 200)

        data = r.json()

        self.assertEqual(data['method'], 'GET')
        self.assertEqual(data['ctx_func_name'], 'return_context')
        self.assertIn('return_context', data['ctx_func_dir'])
        self.assertIn('ctx_invocation_id', data)

    def test_remapped_context(self):
        r = self.webhost.request('GET', 'remapped_context')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'GET')

    def test_return_request(self):
        r = self.webhost.request(
            'GET', 'return_request',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz', 'Max-Forwards': '10'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'GET')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')
        self.assertEqual(req['headers']['max-forwards'], '10')

        self.assertIn('return_request', req['url'])

    def test_post_return_request(self):
        r = self.webhost.request(
            'POST', 'return_request',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz'},
            data={'key': 'value'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')

        self.assertIn('return_request', req['url'])

        self.assertEqual(req['get_body'], 'key=value')

    def test_accept_json(self):
        r = self.webhost.request(
            'POST', 'accept_json',
            json={'a': 'abc', 'd': 42})

        req = r.json()

        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['get_json'], {'a': 'abc', 'd': 42})

        self.assertIn('accept_json', req['url'])

    def test_unhandled_error(self):
        r = self.webhost.request('GET', 'unhandled_error')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertIn('Exception: ZeroDivisionError', r.text)
