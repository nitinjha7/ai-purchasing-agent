from app.db.base import Base, engine


def test_engine_is_configured():
    assert engine is not None
    assert Base.metadata is not None
