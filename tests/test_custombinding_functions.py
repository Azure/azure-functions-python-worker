import hashlib

from azure.functions_worker import testutils


class TestCustomBindingFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'custombinding_functions'

    def test_signalrconnectioninfo_input(self):
        r = self.webhost.request('GET', 'signalrconnectioninfo_input')
        self.assertEqual(r.status_code, 200)
        