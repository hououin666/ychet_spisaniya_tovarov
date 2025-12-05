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
    category_id: int
    supplier_id: Optional[int] = None
    purchase_price: float
    selling_price: float
    current_quantity: int
    min_stock_level: int
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    purchase_price: Optional[float] = None
    selling_price: Optional[float] = None
    current_quantity: Optional[int] = None
    min_stock_level: Optional[int] = None
    description: Optional[str] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WriteOffReasonBase(BaseModel):
    name: str
    description: Optional[str] = None

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

class WriteOff(WriteOffBase):
    id: int
    recorded_by: int
    write_off_date: datetime
    total_loss: float

    class Config:
        from_attributes = True

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