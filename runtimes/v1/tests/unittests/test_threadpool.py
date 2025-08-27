from azure_functions_runtime_v1.utils import threadpool as tp


def _reset():  # helper for clean state
    if tp.get_threadpool_executor() is not None:  # pragma: no cover - cleanup
        tp.stop_threadpool_executor()


def test_start_and_get_threadpool():
    _reset()
    tp.start_threadpool_executor()
    ex = tp.get_threadpool_executor()
    assert ex is not None
    first_id = id(ex)
    tp.start_threadpool_executor()  # restart replaces
    ex2 = tp.get_threadpool_executor()
    assert ex2 is not None and id(ex2) != first_id
    _reset()


def test_stop_threadpool():
    _reset()
    tp.start_threadpool_executor()
    assert tp.get_threadpool_executor() is not None
    tp.stop_threadpool_executor()
    assert tp.get_threadpool_executor() is None


def test_validate_thread_count_invalid(monkeypatch):
    def fake_get_app_setting(setting, validator):
        assert validator("not-int") is False
        return "not-int"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    assert tp._get_max_workers() is None


def test_validate_thread_count_range(monkeypatch):
    def fake_get_app_setting(setting, validator):
        assert validator("0") is False
        return "0"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    assert tp._get_max_workers() == 0


def test_max_workers_valid(monkeypatch):
    def fake_get_app_setting(setting, validator):
        assert validator("10") is True
        return "10"
    monkeypatch.setattr(tp, 'get_app_setting', fake_get_app_setting)
    assert tp._get_max_workers() == 10
