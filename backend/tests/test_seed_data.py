from app.db.models import Product, PurchaseOrder, Supplier
from app.seed_data import seed


def test_seed_creates_expected_rows(db_session):
    seed(db_session)

    assert db_session.query(Product).count() == 3
    assert db_session.query(Supplier).count() == 5
    open_po = db_session.query(PurchaseOrder).filter_by(product_sku="SKU-200").one()
    assert open_po.qty == 500
    assert open_po.status == "submitted"
