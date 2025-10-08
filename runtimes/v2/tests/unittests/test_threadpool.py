# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from azure_functions_runtime.utils import threadpool as tp


def test_start_and_get_threadpool(monkeypatch):
    # Ensure clean state
    if tp._threadpool_executor is not None:  # pragma: no cover - cleanup
        tp.stop_threadpool_executor()
    tp.start_threadpool_executor()
    ex = tp.get_threadpool_executor()
    assert ex is not None
    first_id = id(ex)
    # Starting again replaces it
    tp.start_threadpool_executor()
    ex2 = tp.get_threadpool_executor()
    assert ex2 is not None and id(ex2) != first_id


def test_stop_threadpool():
    tp.start_threadpool_executor()
    assert tp.get_threadpool_executor() is not None
    tp.stop_threadpool_executor()
    assert tp.get_threadpool_executor() is None


def test_validate_thread_count_invalid(monkeypatch):
    # Force invalid value
    def fake_get_app_setting(setting, validator):
        assert validator("not-int") is False
        return "not-int"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    # _get_max_workers should handle invalid and return None
    assert tp._get_max_workers() is None


def test_validate_thread_count_range(monkeypatch):
    # Out of range triggers fallback
    def fake_get_app_setting(setting, validator):
        # Below min
        assert validator("0") is False
        return "0"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    # Since get_app_setting returns the string and _get_max_workers casts it,
    # result becomes 0 (even though validator failed). This documents current behavior.
    assert tp._get_max_workers() == 0


def test_max_workers_valid(monkeypatch):
    def fake_get_app_setting(setting, validator):
        assert validator("10") is True
        return "10"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    assert tp._get_max_workers() == 10
