from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

# Импортируем Base из database
from app.database import Base


class WriteOffStatus(str, enum.Enum):
    PENDING = "pending"  # На рассмотрении
    APPROVED = "approved"  # Утверждено
    REJECTED = "rejected"  # Отклонено
    COMPLETED = "completed"  # Выполнено


class WriteOffApproval(Base):
    __tablename__ = "write_off_approvals"

    id = Column(Integer, primary_key=True, index=True)
    write_off_id = Column(Integer, ForeignKey("write_offs.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_at = Column(DateTime(timezone=True), server_default=func.now())
    decision = Column(Enum(WriteOffStatus), nullable=False)  # APPROVED или REJECTED
    comments = Column(Text)

    write_off = relationship("WriteOff", back_populates="approvals")
    approver = relationship("User", back_populates="write_off_approvals")


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
    write_off_approvals = relationship("WriteOffApproval", back_populates="approver")
    write_off_comments = relationship("WriteOffComment", back_populates="author")


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
    barcode = Column(String(100), unique=True, nullable=True)  # Новое поле: штрих-код
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    purchase_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    current_quantity = Column(Integer, nullable=False, default=0)
    min_stock_level = Column(Integer, nullable=False, default=10)
    location = Column(String(100))  # Новое поле: место хранения
    weight = Column(Float)  # Новое поле: вес
    dimensions = Column(String(50))  # Новое поле: габариты
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
    requires_approval = Column(Boolean, default=True)

class WriteOff(Base):
    __tablename__ = "write_offs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason_id = Column(Integer, ForeignKey("write_off_reasons.id"), nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    write_off_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(WriteOffStatus), default=WriteOffStatus.PENDING, nullable=False)  # Новое поле
    notes = Column(Text)
    total_loss = Column(Float, nullable=False)
    barcode_scanned = Column(Boolean, default=False)  # Новое поле: отсканирован ли штрих-код
    scanned_barcode = Column(String(100))  # Новое поле: отсканированный штрих-код

    product = relationship("Product", back_populates="write_offs")
    reason = relationship("WriteOffReason")
    recorded_by_user = relationship("User", back_populates="write_offs")
    approvals = relationship("WriteOffApproval", back_populates="write_off", cascade="all, delete-orphan")
    comments = relationship("WriteOffComment", back_populates="write_off", cascade="all, delete-orphan")


class WriteOffComment(Base):
    __tablename__ = "write_off_comments"

    id = Column(Integer, primary_key=True, index=True)
    write_off_id = Column(Integer, ForeignKey("write_offs.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_internal = Column(Boolean, default=False)  # Новое поле: внутренний комментарий

    write_off = relationship("WriteOff", back_populates="comments")
    author = relationship("User", back_populates="write_off_comments")


class ProductScan(Base):
    __tablename__ = "product_scans"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    scanned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    scan_type = Column(String(50))  # 'inventory', 'write_off', 'receiving'
    qr_code_data = Column(Text)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())
    location = Column(String(100))  # GPS или локация склада
    device_info = Column(String(200))

    # Relationships
    product = relationship("Product")
    user = relationship("User")


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

    class WriteOffStatusHistory(Base):
        __tablename__ = "write_off_status_history"

        id = Column(Integer, primary_key=True, index=True)
        write_off_id = Column(Integer, ForeignKey("write_offs.id"), nullable=False)
        old_status = Column(Enum(WriteOffStatus))
        new_status = Column(Enum(WriteOffStatus), nullable=False)
        changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
        changed_at = Column(DateTime(timezone=True), server_default=func.now())
        reason = Column(Text)

        write_off = relationship("WriteOff")
        changed_by_user = relationship("User")