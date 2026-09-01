"""Suite-wide fixtures.

Holds only the app-DB fixture, and holds it **non-autouse on purpose**. Before the layer
restructure this file lived inside the on-ramp's own test directory, where blanket
`autouse=True` was correct because every test under it was an on-ramp test. `tests/` is now one tree over all layers,
so an autouse app-DB fixture here would attach the web/ORM stack to every engine test in
`tests/decide/` and `tests/evaluate/` — reintroducing, in the test tree, exactly the coupling the
layer split removes from the source tree.

So: defined here (any layer's tests may *request* `db_sessionmaker` by name), made autouse only in
`tests/surface/conftest.py`, where template rendering opens a DB session on every request and
opt-in would be a silent trap.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_sessionmaker(tmp_path, monkeypatch):
    """Isolated SQLite file under tmp_path with all W5 tables created fresh — never the real
    instance/onramp.db. Yields the sessionmaker so a test can open its own Session to seed rows
    directly, e.g. ``db = db_sessionmaker(); ...; db.close()``.

    Mirrors the store.RAW_DIR monkeypatch convention (tests/surface/test_web_auth.py etc.): patch
    the module attribute the code actually reads at call time, not a name captured at import time.
    """
    import db.engine as db_engine
    from db.models import Base

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_app.db'}", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_engine, "SessionLocal", factory)
    yield factory
    test_engine.dispose()
