from azure.functions_worker import testutils


class TestLoader(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'load_functions'

    def test_loader_simple(self):
        r = self.webhost.request('GET', 'simple')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.simple.main')

    def test_loader_custom_entrypoint(self):
        r = self.webhost.request('GET', 'entrypoint')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.entrypoint.main')

    def test_loader_subdir(self):
        r = self.webhost.request('GET', 'subdir')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.subdir.sub.main')

    def test_loader_relimport(self):
        r = self.webhost.request('GET', 'relimport')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.relimport.relative')
