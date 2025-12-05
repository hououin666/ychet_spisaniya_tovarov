from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from models import Product, Sale, WriteOff
import schemas


# Product CRUD operations
def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Product).offset(skip).limit(limit).all()


def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


def create_product(db: Session, product: schemas.ProductCreate):
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, product_id: int, product: schemas.ProductUpdate):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product:
        for key, value in product.dict().items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product


# Sale CRUD operations
def create_sale(db: Session, sale: schemas.SaleCreate):
    db_sale = Sale(**sale.dict())
    db.add(db_sale)

    # Update product quantity
    product = db.query(Product).filter(Product.id == sale.product_id).first()
    if product:
        product.quantity -= sale.quantity_sold
        if product.quantity < 0:
            product.quantity = 0

    db.commit()
    db.refresh(db_sale)
    return db_sale


def get_sales(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Sale).offset(skip).limit(limit).all()


# Write-off CRUD operations
def create_write_off(db: Session, write_off: schemas.WriteOffCreate):
    db_write_off = WriteOff(**write_off.dict())
    db.add(db_write_off)

    # Update product quantity
    product = db.query(Product).filter(Product.id == write_off.product_id).first()
    if product:
        product.quantity -= write_off.quantity
        if product.quantity < 0:
            product.quantity = 0

    db.commit()
    db.refresh(db_write_off)
    return db_write_off


def get_write_offs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(WriteOff).offset(skip).limit(limit).all()


def get_write_offs_by_product(db: Session, product_id: int):
    return db.query(WriteOff).filter(WriteOff.product_id == product_id).all()


# Analytics functions
def get_analytics(db: Session):
    # Total products and value
    products = db.query(Product).all()
    total_products = len(products)
    total_value = sum(product.price * product.quantity for product in products)

    # Low stock products (less than 10 items)
    low_stock_products = sum(1 for product in products if product.quantity < 10)

    # Top categories
    categories = {}
    for product in products:
        categories[product.category] = categories.get(product.category, 0) + product.quantity

    # Recent sales (last 10)
    recent_sales = db.query(Sale).order_by(desc(Sale.sale_date)).limit(10).all()

    # Recent write-offs (last 10)
    recent_write_offs = db.query(WriteOff).order_by(desc(WriteOff.write_off_date)).limit(10).all()

    # Total losses from write-offs
    total_losses = db.query(func.sum(WriteOff.quantity * Product.price)). \
                       join(Product, WriteOff.product_id == Product.id).scalar() or 0

    return {
        "total_products": total_products,
        "total_value": total_value,
        "low_stock_products": low_stock_products,
        "top_categories": categories,
        "recent_sales": recent_sales,
        "recent_write_offs": recent_write_offs,
        "total_losses": total_losses
    }