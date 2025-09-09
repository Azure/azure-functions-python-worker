# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest

from datetime import datetime
from unittest.mock import patch

from proxy_worker.utils.constants import PYTHON_EOL_DATES
from proxy_worker.utils import common


class TestCheckPythonEOL(unittest.TestCase):
    def setUp(self):
        self.version = "3.13"
        self.eol_date = datetime.strptime(PYTHON_EOL_DATES[self.version], "%Y-%m")
        self.warning_date = self.eol_date.replace(year=2029, month=4, day=1)

    @patch("proxy_worker.utils.common.sys.version_info")
    def test_between_warning_and_eol(self, mock_version):
        mock_version.major, mock_version.minor = (3, 13)
        test_date = datetime(2029, 6, 1)  # Between warning and EOL
        with patch("proxy_worker.utils.common.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = test_date
            mock_datetime.strptime = datetime.strptime
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs)
            with self.assertLogs(level="WARNING") as cm:
                common.check_python_eol()
            self.assertTrue(any("will reach EOL" in msg for msg in cm.output))

    @patch("proxy_worker.utils.common.sys.version_info")
    def test_after_eol(self, mock_version):
        mock_version.major, mock_version.minor = (3, 13)
        test_date = datetime(2030, 1, 1)  # After EOL
        with patch("proxy_worker.utils.common.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = test_date
            mock_datetime.strptime = datetime.strptime
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs)
            with self.assertLogs(level="ERROR") as cm:
                common.check_python_eol()
            self.assertTrue(any("reached EOL" in msg for msg in cm.output))
