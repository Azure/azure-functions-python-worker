# Debug Flags
import pathlib

PYAZURE_WEBHOST_DEBUG = "PYAZURE_WEBHOST_DEBUG"

# E2E Integration Flags and Configurations
PYAZURE_INTEGRATION_TEST = "PYAZURE_INTEGRATION_TEST"
PYAZURE_WORKER_DIR = "PYAZURE_WORKER_DIR"
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
UNIT_TESTS_FOLDER = pathlib.Path('unittests')
STEIN_TESTS_ROOT = PROJECT_ROOT / 'tests' / 'stein_tests'
UNIT_TESTS_ROOT = STEIN_TESTS_ROOT / UNIT_TESTS_FOLDER
WORKER_PATH = PROJECT_ROOT / 'python' / 'test'
WORKER_CONFIG = PROJECT_ROOT / '.testconfig'
LOCALHOST = "127.0.0.1"
HTTP_FUNCS_PATH = UNIT_TESTS_ROOT / 'http_functions'
TIMER_FUNCS_PATH = UNIT_TESTS_ROOT / 'timer_functions'
DISPATCHER_FUNCTIONS_DIR = UNIT_TESTS_ROOT / 'dispatcher_functions'
E2E_TESTS_FOLDER = pathlib.Path('endtoendtests')
E2E_TESTS_ROOT = STEIN_TESTS_ROOT / E2E_TESTS_FOLDER