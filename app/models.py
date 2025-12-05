from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

# Импортируем Base из database
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    write_offs = relationship("WriteOff", back_populates="recorded_by_user")
    sales = relationship("Sale", back_populates="recorded_by_user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)

    products = relationship("Product", back_populates="category_rel")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact_email = Column(String(255))
    phone = Column(String(20))
    address = Column(Text)

    products = relationship("Product", back_populates="supplier_rel")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    sku = Column(String(50), unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    purchase_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    current_quantity = Column(Integer, nullable=False, default=0)
    min_stock_level = Column(Integer, nullable=False, default=10)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category_rel = relationship("Category", back_populates="products")
    supplier_rel = relationship("Supplier", back_populates="products")
    sales = relationship("Sale", back_populates="product")
    write_offs = relationship("WriteOff", back_populates="product")


class WriteOffReason(Base):
    __tablename__ = "write_off_reasons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)


class WriteOff(Base):
    __tablename__ = "write_offs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason_id = Column(Integer, ForeignKey("write_off_reasons.id"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    write_off_date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text)
    total_loss = Column(Float, nullable=False)

    product = relationship("Product", back_populates="write_offs")
    reason = relationship("WriteOffReason")
    recorded_by_user = relationship("User", back_populates="write_offs")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_sold = Column(Integer, nullable=False)
    sale_price = Column(Float, nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    sale_date = Column(DateTime(timezone=True), server_default=func.now())
    customer_info = Column(Text)

    product = relationship("Product", back_populates="sales")
    recorded_by_user = relationship("User", back_populates="sales")