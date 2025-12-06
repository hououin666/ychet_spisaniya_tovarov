from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True

class SupplierBase(BaseModel):
    name: str
    contact_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class Supplier(SupplierBase):
    id: int

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    sku: str
    barcode: Optional[str] = None
    category_id: int
    supplier_id: Optional[int] = None
    purchase_price: float
    selling_price: float
    current_quantity: int
    min_stock_level: int
    location: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    purchase_price: Optional[float] = None
    selling_price: Optional[float] = None
    current_quantity: Optional[int] = None
    min_stock_level: Optional[int] = None
    location: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None
    description: Optional[str] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    category_rel: Optional[Category] = None
    supplier_rel: Optional[Supplier] = None

    class Config:
        from_attributes = True

class WriteOffReasonBase(BaseModel):
    name: str
    description: Optional[str] = None
    requires_approval: bool = True


class WriteOffReasonCreate(WriteOffReasonBase):
    pass

class WriteOffReason(WriteOffReasonBase):
    id: int

    class Config:
        from_attributes = True


class WriteOffBase(BaseModel):
    product_id: int
    quantity: int
    reason_id: int
    notes: Optional[str] = None

class WriteOffCreate(WriteOffBase):
    pass


class SaleBase(BaseModel):
    product_id: int
    quantity_sold: int
    sale_price: float
    customer_info: Optional[str] = None

class SaleCreate(SaleBase):
    pass

class Sale(SaleBase):
    id: int
    recorded_by: int
    sale_date: datetime

    class Config:
        from_attributes = True



class WriteOffStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

# Комментарии
class WriteOffCommentBase(BaseModel):
    comment: str
    attachment_url: Optional[str] = None

class WriteOffCommentCreate(WriteOffCommentBase):
    write_off_id: int

class WriteOffComment(WriteOffCommentBase):
    id: int
    write_off_id: int
    user_id: int
    created_at: datetime
    user: Optional[User] = None

    class Config:
        from_attributes = True

# Подтверждения
class WriteOffApprovalBase(BaseModel):
    write_off_id: int
    status: WriteOffStatus
    comments: Optional[str] = None

class WriteOffApprovalCreate(WriteOffApprovalBase):
    pass

class WriteOffApproval(WriteOffApprovalBase):
    id: int
    approver_id: int
    approved_at: Optional[datetime] = None
    created_at: datetime
    approver: Optional[User] = None

    class Config:
        from_attributes = True

# Сканирование
class ProductScanBase(BaseModel):
    product_id: int
    scan_type: str
    qr_code_data: str
    location: Optional[str] = None
    device_info: Optional[str] = None

class ProductScanCreate(ProductScanBase):
    pass

class ProductScan(ProductScanBase):
    id: int
    scanned_by: int
    scanned_at: datetime
    product: Optional[Product] = None
    user: Optional[User] = None

    class Config:
        from_attributes = True


class WriteOff(WriteOffBase):
    id: int
    recorded_by: int
    write_off_date: datetime
    total_loss: float
    status: WriteOffStatus
    requires_approval: bool
    approval_threshold: float
    product: Optional[Product] = None
    reason: Optional[WriteOffReason] = None
    recorded_by_user: Optional[User] = None
    comments: List[WriteOffComment] = []
    approvals: List[WriteOffApproval] = []

    class Config:
        from_attributes = True

class AnalyticsResponse(BaseModel):
    total_products: int
    total_inventory_value: float
    low_stock_products: int
    total_write_offs: int
    total_losses: float
    total_sales: int
    total_revenue: float
    top_categories: dict
    recent_write_offs: List[WriteOff]
    recent_sales: List[Sale]
