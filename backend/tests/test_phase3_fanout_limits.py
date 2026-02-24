from __future__ import annotations

from typing import Any, Dict, List
import sys
import types

# Stubs livianos para evitar dependencias pesadas durante unit tests de lógica.
if "pymongo" not in sys.modules:
    pymongo_stub = types.ModuleType("pymongo")
    pymongo_stub.MongoClient = object  # type: ignore[attr-defined]
    pymongo_stub.UpdateOne = object  # type: ignore[attr-defined]
    sys.modules["pymongo"] = pymongo_stub

if "pymongo.collection" not in sys.modules:
    pymongo_collection_stub = types.ModuleType("pymongo.collection")
    pymongo_collection_stub.Collection = object  # type: ignore[attr-defined]
    sys.modules["pymongo.collection"] = pymongo_collection_stub

if "bson" not in sys.modules:
    bson_stub = types.ModuleType("bson")

    class _ObjectId(str):
        pass

    bson_stub.ObjectId = _ObjectId  # type: ignore[attr-defined]
    sys.modules["bson"] = bson_stub

if "app.modules.openai_processor.openai_processor" not in sys.modules:
    openai_processor_stub = types.ModuleType("app.modules.openai_processor.openai_processor")

    class _DummyOpenAIProcessor:
        pass

    openai_processor_stub.OpenAIProcessor = _DummyOpenAIProcessor  # type: ignore[attr-defined]
    sys.modules["app.modules.openai_processor.openai_processor"] = openai_processor_stub

if "app.modules.email_processor.config_store" not in sys.modules:
    config_store_stub = types.ModuleType("app.modules.email_processor.config_store")

    def _empty_configs(*args: Any, **kwargs: Any):
        return []

    config_store_stub.get_enabled_configs = _empty_configs  # type: ignore[attr-defined]
    sys.modules["app.modules.email_processor.config_store"] = config_store_stub

if "app.modules.scheduler.job_runner" not in sys.modules:
    job_runner_stub = types.ModuleType("app.modules.scheduler.job_runner")

    class _DummyScheduledJobRunner:
        def __init__(self, *args: Any, **kwargs: Any):
            self.is_running = False
            self.next_run = None
            self.last_run = None
            self.last_result = None
            self.interval_minutes = kwargs.get("interval_minutes", 60)

        def start(self):
            self.is_running = True

        def stop(self):
            self.is_running = False

        def is_alive(self):
            return False

    job_runner_stub.ScheduledJobRunner = _DummyScheduledJobRunner  # type: ignore[attr-defined]
    sys.modules["app.modules.scheduler.job_runner"] = job_runner_stub

from app.config.settings import settings
from app.models.models import MultiEmailConfig, ProcessResult
from app.modules.email_processor import multi_processor as mp_module
from app.modules.email_processor.multi_processor import MultiEmailProcessor


class _FakeUserRepository:
    def can_use_ai(self, owner_email: str) -> Dict[str, Any]:
        return {"can_use": True, "message": "ok"}

    def get_trial_info(self, owner_email: str) -> Dict[str, Any]:
        return {
            "is_trial_user": False,
            "ai_invoices_limit": -1,
            "ai_invoices_processed": 0,
        }


class _FakeEmailProcessor:
    calls: List[Dict[str, Any]] = []

    def __init__(self, config: Any, owner_email: str | None = None):
        self.config = config
        self.owner_email = owner_email

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        return None

    def process_emails(self, **kwargs: Any) -> ProcessResult:
        _FakeEmailProcessor.calls.append(kwargs)
        queued = int(kwargs.get("max_discovery_emails") or 0)
        return ProcessResult(
            success=True,
            message="fanout-ok",
            invoice_count=queued,
            invoices=[],
        )

    def search_emails(self, **kwargs: Any) -> List[Dict[str, Any]]:
        return []


def _make_config(username: str, owner: str = "owner@test.py") -> MultiEmailConfig:
    return MultiEmailConfig(
        host="imap.test.py",
        port=993,
        username=username,
        password="secret",
        owner_email=owner,
        search_terms=["factura"],
    )


def test_manual_fanout_respects_global_limit(monkeypatch):
    monkeypatch.setattr(mp_module, "EmailProcessor", _FakeEmailProcessor)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository", _FakeUserRepository)
    monkeypatch.setattr(settings, "FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 200, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_DEFAULT_LIMIT", 50, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_MAX_LIMIT", 200, raising=False)

    _FakeEmailProcessor.calls = []
    processor = MultiEmailProcessor(
        email_configs=[
            _make_config("acc1@test.py"),
            _make_config("acc2@test.py"),
            _make_config("acc3@test.py"),
        ],
        owner_email="owner@test.py",
    )

    result = processor.process_limited_emails(limit=70, fan_out=True)

    assert result.success is True
    assert result.invoice_count == 70
    # Cuenta 1 recibe 70, luego se detiene el loop global.
    assert _FakeEmailProcessor.calls[0]["max_discovery_emails"] == 70
    assert len(_FakeEmailProcessor.calls) == 1


def test_manual_fanout_respects_per_account_cap(monkeypatch):
    monkeypatch.setattr(mp_module, "EmailProcessor", _FakeEmailProcessor)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository", _FakeUserRepository)
    monkeypatch.setattr(settings, "FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 50, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_DEFAULT_LIMIT", 50, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_MAX_LIMIT", 200, raising=False)

    _FakeEmailProcessor.calls = []
    processor = MultiEmailProcessor(
        email_configs=[
            _make_config("acc1@test.py"),
            _make_config("acc2@test.py"),
            _make_config("acc3@test.py"),
        ],
        owner_email="owner@test.py",
    )

    result = processor.process_limited_emails(limit=120, fan_out=True)

    assert result.success is True
    # 50 + 50 + 20 = 120 exactos con cap por cuenta + cap global.
    assert result.invoice_count == 120
    assert [c["max_discovery_emails"] for c in _FakeEmailProcessor.calls] == [50, 50, 20]


def test_manual_fanout_applies_default_and_max_limit(monkeypatch):
    monkeypatch.setattr(mp_module, "EmailProcessor", _FakeEmailProcessor)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository", _FakeUserRepository)
    monkeypatch.setattr(settings, "FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 500, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_DEFAULT_LIMIT", 50, raising=False)
    monkeypatch.setattr(settings, "PROCESS_DIRECT_MAX_LIMIT", 200, raising=False)

    processor = MultiEmailProcessor(
        email_configs=[_make_config("acc1@test.py")],
        owner_email="owner@test.py",
    )

    _FakeEmailProcessor.calls = []
    result_default = processor.process_limited_emails(limit=None, fan_out=True)
    assert result_default.invoice_count == 50
    assert _FakeEmailProcessor.calls[0]["max_discovery_emails"] == 50

    _FakeEmailProcessor.calls = []
    result_capped = processor.process_limited_emails(limit=1000, fan_out=True)
    assert result_capped.invoice_count == 200
    assert _FakeEmailProcessor.calls[0]["max_discovery_emails"] == 200
