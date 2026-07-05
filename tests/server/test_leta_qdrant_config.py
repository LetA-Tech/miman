"""LetA server-patch regression suite (spec 03-M §9.4, T-1..T-17).

Covers the only Python-code delta miman layers over upstream Mem0:
  - env-driven vector-store selection + Qdrant config builder (§5.1-5.2)
  - /healthz + /readyz + request-log skip (§5.3)
  - fail-closed boot probe (§5.2)
  - member-credential provisioning script (§3.4 delta-6)

Every test is hermetic: no live Postgres/Qdrant/network. `mem0.Memory.from_config`
is patched at import so the server boots against a MagicMock backend; the two
core-path tests (T-10 base-url, T-13 infer=false) construct real objects with
their I/O collaborators mocked.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"

# Every server-affecting env var the loader clears before each reload, so one
# test's environment never leaks into the next (import-time reads, §5.1-5.2).
SERVER_ENV_KEYS = (
    "ADMIN_API_KEY",
    "AUTH_DISABLED",
    "JWT_SECRET",
    "MEM0_VECTOR_STORE",
    "QDRANT_URL",
    "QDRANT_HOST",
    "QDRANT_PORT",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION_NAME",
    "QDRANT_EMBEDDING_MODEL_DIMS",
    "QDRANT_ON_DISK",
    "MIMAN_ENV",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_COLLECTION_NAME",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "MEM0_DEFAULT_LLM_MODEL",
    "MEM0_DEFAULT_EMBEDDER_MODEL",
    "MEM0_API_KEY",
)

SERVER_MODULES = (
    "auth",
    "db",
    "errors",
    "models",
    "rate_limit",
    "schemas",
    "server.main",
    "server_state",
    "telemetry",
)


def _purge_server_modules():
    for name in list(sys.modules):
        if name in SERVER_MODULES or name.startswith("routers"):
            del sys.modules[name]


def _load_server(monkeypatch, env, memory=None):
    """Reload server.main under `env` with Memory.from_config patched.

    Returns (module, from_config_mock, memory_mock). `memory` lets a test inject
    a pre-wired backend mock (e.g. get_collections raising, for the boot probe).
    """
    monkeypatch.syspath_prepend(str(SERVER_DIR))
    for key in SERVER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    _purge_server_modules()
    memory = memory or MagicMock()
    with patch("mem0.Memory.from_config", return_value=memory) as from_config:
        module = importlib.import_module("server.main")
    return module, from_config, memory


def _qdrant_env(**overrides):
    """Canonical LetA qdrant profile env (mirrors deprecated _option_b_env,
    read-only reference). MIMAN_ENV=local so the fail-closed boot probe is
    inert for every test except T-15, which overrides it."""
    env = {
        "AUTH_DISABLED": "true",
        "MIMAN_ENV": "local",
        "MEM0_VECTOR_STORE": "qdrant",
        "QDRANT_URL": "http://qdrant:6333",
        "QDRANT_API_KEY": "qdrant-secret",
        "QDRANT_COLLECTION_NAME": "internal_coding_prod_mellions_memory_e3small_v1",
        "OPENAI_API_KEY": "fake-key",
        "POSTGRES_HOST": "appdb",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "mem0_app",
        "POSTGRES_USER": "mem0",
        "POSTGRES_PASSWORD": "test-postgres-password",
    }
    env.update(overrides)
    return env


def _pg_env(**overrides):
    """Minimal env for the default (pgvector) path. AUTH_DISABLED satisfies the
    boot auth guard (main.py:89) so import reaches the selector."""
    env = {"OPENAI_API_KEY": "fake-key", "AUTH_DISABLED": "true"}
    env.update(overrides)
    return env


def _resolved_config(from_config):
    return from_config.call_args.args[0]


# ---------------------------------------------------------------------------
# R1 — selection contract (§5.1) — T-1, T-2, T-7
# ---------------------------------------------------------------------------

def test_t1_unset_defaults_to_pgvector(monkeypatch):
    _, from_config, _ = _load_server(monkeypatch, _pg_env())
    vs = _resolved_config(from_config)["vector_store"]
    assert vs["provider"] == "pgvector"
    assert set(vs["config"]) == {"host", "port", "dbname", "user", "password", "collection_name"}
    assert isinstance(vs["config"]["port"], int)


def test_t2_pgvector_explicit_is_upstream_parity(monkeypatch):
    unset, _, _ = _load_server(monkeypatch, _pg_env())
    default_vs = unset.DEFAULT_CONFIG["vector_store"]
    explicit, from_config, _ = _load_server(monkeypatch, _pg_env(MEM0_VECTOR_STORE="pgvector"))
    assert _resolved_config(from_config)["vector_store"] == default_vs


def test_t2_selection_trims_and_lowercases(monkeypatch):
    _, from_config, _ = _load_server(monkeypatch, _pg_env(MEM0_VECTOR_STORE="  PgVector  "))
    assert _resolved_config(from_config)["vector_store"]["provider"] == "pgvector"


def test_t7_unsupported_value_raises_naming_supported(monkeypatch):
    with pytest.raises(RuntimeError) as exc:
        _load_server(monkeypatch, _pg_env(MEM0_VECTOR_STORE="weaviate"))
    msg = str(exc.value)
    assert "pgvector" in msg and "qdrant" in msg


# ---------------------------------------------------------------------------
# R2 — Qdrant config builder (§5.2) — T-3, T-4, T-5, T-6
# ---------------------------------------------------------------------------

def test_t3_url_with_api_key_passes_through(monkeypatch):
    _, from_config, _ = _load_server(monkeypatch, _qdrant_env())
    cfg = _resolved_config(from_config)["vector_store"]
    assert cfg["provider"] == "qdrant"
    assert cfg["config"]["url"] == "http://qdrant:6333"
    assert cfg["config"]["api_key"] == "qdrant-secret"
    assert "host" not in cfg["config"] and "port" not in cfg["config"]


def test_t4_url_without_api_key_decomposes_and_validates(monkeypatch):
    from mem0.configs.vector_stores.qdrant import QdrantConfig

    _, from_config, _ = _load_server(monkeypatch, _qdrant_env(QDRANT_API_KEY=""))
    cfg = _resolved_config(from_config)["vector_store"]["config"]
    # validator quirk §3.3: url-without-key must be decomposed to host/port
    assert "url" not in cfg
    assert cfg["host"] == "qdrant"
    assert cfg["port"] == 6333
    # the decomposed config must satisfy the real before-validator (qdrant.py:35)
    QdrantConfig(**cfg)


def test_t4_https_url_without_api_key_sets_https_and_443(monkeypatch):
    _, from_config, _ = _load_server(
        monkeypatch, _qdrant_env(QDRANT_URL="https://vecdb.example.com", QDRANT_API_KEY="")
    )
    cfg = _resolved_config(from_config)["vector_store"]["config"]
    assert cfg["host"] == "vecdb.example.com"
    assert cfg["port"] == 443
    assert cfg["https"] is True


def test_t4_unparseable_url_without_api_key_fails_fast(monkeypatch):
    with pytest.raises(RuntimeError):
        _load_server(monkeypatch, _qdrant_env(QDRANT_URL="not a url", QDRANT_API_KEY=""))


def test_t5_host_port_fallback_int_converts(monkeypatch):
    _, from_config, _ = _load_server(
        monkeypatch, _qdrant_env(QDRANT_URL="", QDRANT_HOST="qdrant", QDRANT_PORT="6333")
    )
    cfg = _resolved_config(from_config)["vector_store"]["config"]
    assert cfg["host"] == "qdrant"
    assert cfg["port"] == 6333 and isinstance(cfg["port"], int)


def test_t5_garbage_port_fails_fast(monkeypatch):
    with pytest.raises((RuntimeError, ValueError)):
        _load_server(monkeypatch, _qdrant_env(QDRANT_URL="", QDRANT_HOST="qdrant", QDRANT_PORT="abc"))


def test_t5_qdrant_without_any_target_fails_fast(monkeypatch):
    with pytest.raises(RuntimeError):
        _load_server(monkeypatch, _qdrant_env(QDRANT_URL="", QDRANT_API_KEY=""))


def test_t6_dims_and_on_disk_coercions(monkeypatch):
    _, from_config, _ = _load_server(
        monkeypatch, _qdrant_env(QDRANT_EMBEDDING_MODEL_DIMS="1536", QDRANT_ON_DISK="yes")
    )
    cfg = _resolved_config(from_config)["vector_store"]["config"]
    assert cfg["embedding_model_dims"] == 1536 and isinstance(cfg["embedding_model_dims"], int)
    assert cfg["on_disk"] is True


def test_t6_on_disk_defaults_false_and_truthy_set_exact(monkeypatch):
    _, from_config, _ = _load_server(monkeypatch, _qdrant_env())
    assert _resolved_config(from_config)["vector_store"]["config"]["on_disk"] is False
    _, from_config2, _ = _load_server(monkeypatch, _qdrant_env(QDRANT_ON_DISK="False"))
    assert _resolved_config(from_config2)["vector_store"]["config"]["on_disk"] is False


def test_t3_never_sets_path(monkeypatch):
    # path selects embedded local mode — must never appear (§5.2)
    for env in (_qdrant_env(), _qdrant_env(QDRANT_API_KEY="")):
        _, from_config, _ = _load_server(monkeypatch, env)
        assert "path" not in _resolved_config(from_config)["vector_store"]["config"]


# ---------------------------------------------------------------------------
# R3/R4 — health endpoints + log skip (§5.3) — T-8, T-9, T-12
# ---------------------------------------------------------------------------

def test_t8_healthz_ok_unauthenticated(monkeypatch):
    module, _, _ = _load_server(monkeypatch, _qdrant_env(AUTH_DISABLED="false", JWT_SECRET="x" * 40))
    resp = TestClient(module.app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_t9_readyz_ready_when_db_query_succeeds(monkeypatch):
    module, _, _ = _load_server(monkeypatch, _qdrant_env())

    class ReadySession:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, _stmt):
            return None

    monkeypatch.setattr(module, "SessionLocal", lambda: ReadySession())
    resp = TestClient(module.app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_t9_readyz_not_ready_when_db_query_fails(monkeypatch):
    module, _, _ = _load_server(monkeypatch, _qdrant_env())

    class FailingSession:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, _stmt):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(module, "SessionLocal", lambda: FailingSession())
    resp = TestClient(module.app).get("/readyz")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready"}


def test_t12_health_paths_are_not_request_logged(monkeypatch):
    module, _, _ = _load_server(monkeypatch, _qdrant_env())

    def _req(path):
        r = MagicMock()
        r.method = "GET"
        r.url.path = path
        return r

    assert module._should_log_request(_req("/healthz")) is False
    assert module._should_log_request(_req("/readyz")) is False
    assert module._should_log_request(_req("/memories")) is True


# ---------------------------------------------------------------------------
# R7 — OPENAI_BASE_URL honored by core, no server config keys (§3.2, D-2) — T-10
# ---------------------------------------------------------------------------

def test_t10_openai_base_url_honored_by_core_llm_and_embedder(monkeypatch):
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

    from mem0.configs.embeddings.base import BaseEmbedderConfig
    from mem0.embeddings.openai import OpenAIEmbedding
    from mem0.llms.openai import OpenAILLM

    llm = OpenAILLM({"api_key": "fake-key"})
    embedder = OpenAIEmbedding(BaseEmbedderConfig(api_key="fake-key"))

    assert "openrouter.ai/api/v1" in str(llm.client.base_url)
    assert "openrouter.ai/api/v1" in str(embedder.client.base_url)


def test_t10_server_config_does_not_inject_base_url(monkeypatch):
    # D-2: the server must NOT re-add openai_base_url forwarding
    _, from_config, _ = _load_server(
        monkeypatch, _qdrant_env(OPENAI_BASE_URL="https://openrouter.ai/api/v1")
    )
    cfg = _resolved_config(from_config)
    assert "openai_base_url" not in cfg["llm"]["config"]
    assert "openai_base_url" not in cfg["embedder"]["config"]


# ---------------------------------------------------------------------------
# R8 — /search both shapes reach identical filters (§3.1, D-1) — T-11
# ---------------------------------------------------------------------------

def test_t11_search_top_level_and_filters_produce_identical_filters(monkeypatch):
    memory = MagicMock()
    memory.search.return_value = [{"id": "m1", "memory": "x", "score": 0.9}]
    module, _, _ = _load_server(monkeypatch, _qdrant_env(), memory=memory)
    client = TestClient(module.app)

    client.post("/search", json={"query": "q", "user_id": "alice"})
    top_level_filters = memory.search.call_args.kwargs["filters"]

    memory.search.reset_mock()
    client.post("/search", json={"query": "q", "filters": {"user_id": "alice"}})
    wrapped_filters = memory.search.call_args.kwargs["filters"]

    assert top_level_filters == wrapped_filters == {"user_id": "alice"}


# ---------------------------------------------------------------------------
# R9 — infer=false single-record invariant (§3.5, §7.4) — T-13
# ---------------------------------------------------------------------------

def test_t13_infer_false_yields_exactly_one_add_per_non_system_message():
    from mem0.memory.main import Memory

    mem = Memory.__new__(Memory)  # bypass __init__; exercise the real add loop only
    mem.embedding_model = MagicMock()
    mem.embedding_model.embed.return_value = [0.1] * 8
    mem.vector_store = MagicMock()
    mem.db = MagicMock()

    one = mem._add_to_vector_store(
        [{"role": "user", "content": "hi"}], metadata={}, filters={"user_id": "u"}, infer=False
    )
    assert len(one) == 1
    assert one[0]["event"] == "ADD"

    # system messages are skipped — still exactly one record
    with_system = mem._add_to_vector_store(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        metadata={},
        filters={"user_id": "u"},
        infer=False,
    )
    assert len(with_system) == 1
    assert with_system[0]["event"] == "ADD"


# ---------------------------------------------------------------------------
# R10 — no MEM0_API_KEY in canonical config (§9.4 T-14)
# ---------------------------------------------------------------------------

def test_t14_no_mem0_api_key_in_canonical_config(monkeypatch):
    _, from_config, _ = _load_server(monkeypatch, _qdrant_env(MEM0_API_KEY="cloud-key"))
    cfg = _resolved_config(from_config)
    assert "cloud-key" not in repr(cfg)
    assert "MEM0_API_KEY" not in repr(cfg)


# ---------------------------------------------------------------------------
# R5 — fail-closed boot probe (§5.2) — T-15
# ---------------------------------------------------------------------------

def test_t15_boot_probe_fails_closed_in_prod(monkeypatch):
    memory = MagicMock()
    memory.vector_store.client.get_collections.side_effect = ConnectionError("unreachable")
    module, _, _ = _load_server(monkeypatch, _qdrant_env(MIMAN_ENV="prod"), memory=memory)

    # startup raising aborts boot; uvicorn translates this to a non-zero process exit
    with pytest.raises(RuntimeError):
        with TestClient(module.app):
            pass
    memory.vector_store.client.get_collections.assert_called_once()


def test_t15_boot_probe_warns_only_in_local(monkeypatch):
    memory = MagicMock()
    memory.vector_store.client.get_collections.side_effect = ConnectionError("unreachable")
    module, _, _ = _load_server(monkeypatch, _qdrant_env(MIMAN_ENV="local"), memory=memory)

    # local: startup must not abort even though the probe target is unreachable
    with TestClient(module.app):
        pass


def test_t15_boot_probe_skipped_for_pgvector(monkeypatch):
    memory = MagicMock()
    module, _, _ = _load_server(monkeypatch, _pg_env(MIMAN_ENV="prod"), memory=memory)
    with TestClient(module.app):
        pass
    memory.vector_store.client.get_collections.assert_not_called()


# ---------------------------------------------------------------------------
# R6 — member-credential provisioning script (§3.4 delta-6) — T-16, T-17
# ---------------------------------------------------------------------------

@pytest.fixture
def provision_mod(monkeypatch):
    """Import the provisioning script with SessionLocal bound to in-memory SQLite."""
    monkeypatch.syspath_prepend(str(SERVER_DIR))
    for name in list(sys.modules):
        if name in ("auth", "db", "models", "scripts.provision_service_key") or name.startswith("scripts"):
            del sys.modules[name]

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from db import Base
    import models  # noqa: F401 — registers tables on Base.metadata

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    import importlib as _il

    mod = _il.import_module("scripts.provision_service_key")
    monkeypatch.setattr(mod, "SessionLocal", TestSession)
    return mod, TestSession


def test_t16_provision_creates_member_user_and_key(provision_mod):
    mod, TestSession = provision_mod
    with TestSession() as db:
        full_key, created = mod.provision(db, name="finsor-runtime", label="finsor prod")
    assert created is True
    assert full_key.startswith("m0sk_")

    from models import APIKey, User
    from sqlalchemy import select

    with TestSession() as db:
        user = db.scalar(select(User).where(User.name == "finsor-runtime"))
        assert user is not None
        assert user.role == "member"
        keys = db.execute(select(APIKey).where(APIKey.created_by == user.id)).scalars().all()
        assert len(keys) == 1


def test_t17_member_key_resolves_to_member_and_would_403_on_admin(provision_mod):
    mod, TestSession = provision_mod
    with TestSession() as db:
        full_key, _ = mod.provision(db, name="finsor-runtime", label="finsor prod")

    from auth import _resolve_user_from_api_key

    with TestSession() as db:
        resolved = _resolve_user_from_api_key(full_key, db)
    assert resolved.role == "member"
    # require_admin (auth.py:213-214) raises 403 for exactly this condition
    assert resolved.role != "admin"


def test_t16_duplicate_without_rotate_refuses_and_mints_nothing(provision_mod):
    mod, TestSession = provision_mod
    with TestSession() as db:
        mod.provision(db, name="finsor-runtime", label="finsor prod")
    with TestSession() as db:
        with pytest.raises(ValueError):
            mod.provision(db, name="finsor-runtime", label="second")

    from models import APIKey
    from sqlalchemy import func, select

    with TestSession() as db:
        assert db.scalar(select(func.count(APIKey.id))) == 1


def test_t16_rotate_mints_new_key_only_no_new_user(provision_mod):
    mod, TestSession = provision_mod
    with TestSession() as db:
        mod.provision(db, name="finsor-runtime", label="finsor prod")
    with TestSession() as db:
        full_key, created = mod.provision(db, name="finsor-runtime", label="rotated", rotate=True)
    assert created is False
    assert full_key.startswith("m0sk_")

    from models import APIKey, User
    from sqlalchemy import func, select

    with TestSession() as db:
        assert db.scalar(select(func.count(User.id))) == 1
        assert db.scalar(select(func.count(APIKey.id))) == 2
