from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.models import Response
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime

from analytics import InventoryAnalytics
from app.database import get_db, engine, Base, SessionLocal
from app import models
from app import schemas
from app import auth
from dependecies import get_current_admin, get_current_manager, get_analytics_service
from app.patterns.repository import ProductRepository, WriteOffRepository
from app.patterns.observer import InventorySubject, LowStockNotifier, LossAnalyticsObserver


def initialize_database():
    """Инициализация базы данных начальными данными"""
    db = SessionLocal()
    try:
        # Создаем категории
        categories = [
            models.Category(name="Электроника", description="Электронные устройства"),
            models.Category(name="Одежда", description="Одежда и аксессуары"),
            models.Category(name="Продукты", description="Продовольственные товары"),
            models.Category(name="Книги", description="Книги и журналы"),
        ]

        for category in categories:
            if not db.query(models.Category).filter(models.Category.name == category.name).first():
                db.add(category)

        # Создаем причины списания
        reasons = [
            models.WriteOffReason(name="Порча", description="Товар испортился"),
            models.WriteOffReason(name="Брак", description="Производственный брак"),
            models.WriteOffReason(name="Истек срок", description="Истек срок годности"),
            models.WriteOffReason(name="Повреждение", description="Повреждение при транспортировке"),
        ]

        for reason in reasons:
            if not db.query(models.WriteOffReason).filter(models.WriteOffReason.name == reason.name).first():
                db.add(reason)

        # Создаем администратора
        admin_user = db.query(models.User).filter(models.User.email == "admin@example.com").first()
        if not admin_user:
            hashed_password = auth.get_password_hash("admin123")
            admin_user = models.User(
                email="admin@example.com",
                hashed_password=hashed_password,
                full_name="Administrator",
                role=models.UserRole.ADMIN
            )
            db.add(admin_user)

        # Создаем тестового пользователя
        test_user = db.query(models.User).filter(models.User.email == "user@example.com").first()
        if not test_user:
            hashed_password = auth.get_password_hash("user123")
            test_user = models.User(
                email="user@example.com",
                hashed_password=hashed_password,
                full_name="Test User",
                role=models.UserRole.USER
            )
            db.add(test_user)

        # Создаем тестового менеджера
        manager_user = db.query(models.User).filter(models.User.email == "manager@example.com").first()
        if not manager_user:
            hashed_password = auth.get_password_hash("manager123")
            manager_user = models.User(
                email="manager@example.com",
                hashed_password=hashed_password,
                full_name="Test Manager",
                role=models.UserRole.MANAGER
            )
            db.add(manager_user)

        db.commit()
        print("✓ Database initialized successfully!")
        print("  Admin: admin@example.com / admin123")
        print("  Manager: manager@example.com / manager123")
        print("  User: user@example.com / user123")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    print("🚀 Starting up Inventory Management API...")
    print("📊 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("📝 Initializing database with sample data...")
    initialize_database()
    print("✅ Application started successfully!")
    print("\n🌐 API доступен по адресу: http://localhost:8000")
    print("📚 Документация API: http://localhost:8000/docs")
    print("📖 ReDoc: http://localhost:8000/redoc")
    yield
    # Shutdown code
    print("👋 Shutting down Inventory Management API...")


app = FastAPI(
    title="Inventory Management API",
    description="Система автоматизации учета списания товаров",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# Фабрики для репозиториев и наблюдателей
def get_product_repository(db: Session = Depends(get_db)):
    return ProductRepository(db)


def get_write_off_repository(db: Session = Depends(get_db)):
    return WriteOffRepository(db)


def get_inventory_subject(db: Session = Depends(get_db)):
    subject = InventorySubject()
    subject.attach(LowStockNotifier(db))
    subject.attach(LossAnalyticsObserver(db))
    return subject


@app.post("/auth/register", response_model=schemas.User)
def register(
        user: schemas.UserCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_admin())
):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/auth/login", response_model=schemas.Token)
def login(
        form_data: schemas.UserLogin,
        db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.email, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(
        data={"sub": user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user


@app.post("/products/", response_model=schemas.Product)
def create_product(
        product: schemas.ProductCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_manager()),
        product_repo: ProductRepository = Depends(get_product_repository)
):
    if product_repo.get_by_sku(product.sku):
        raise HTTPException(status_code=400, detail="SKU already exists")

    return product_repo.create(product.dict())


@app.get("/products/", response_model=List[schemas.Product])
def read_products(
        skip: int = 0,
        limit: int = 100,
        product_repo: ProductRepository = Depends(get_product_repository),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return product_repo.get_all(skip=skip, limit=limit)

@app.get("/products/low-stock", response_model=List[schemas.Product])
def read_low_stock_products(
        product_repo: ProductRepository = Depends(get_product_repository),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    return product_repo.get_low_stock()


@app.get("/products/{product_id}", response_model=schemas.Product)
def read_product(
        product_id: int,
        product_repo: ProductRepository = Depends(get_product_repository),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    product = product_repo.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.put("/products/{product_id}", response_model=schemas.Product)
def update_product(
        product_id: int,
        product_update: schemas.ProductUpdate,
        product_repo: ProductRepository = Depends(get_product_repository),
        current_user: models.User = Depends(get_current_manager())
):
    product = product_repo.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_update.dict(exclude_unset=True)
    if 'sku' in update_data and update_data['sku'] != product.sku:
        existing = product_repo.get_by_sku(update_data['sku'])
        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")

    return product_repo.update(product, update_data)


@app.delete("/products/{product_id}")
def delete_product(
        product_id: int,
        product_repo: ProductRepository = Depends(get_product_repository),
        current_user: models.User = Depends(get_current_manager())
):
    success = product_repo.delete(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}




@app.post("/write-offs/", response_model=schemas.WriteOff)
def create_write_off(
        write_off: schemas.WriteOffCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user),
        product_repo: ProductRepository = Depends(get_product_repository),
        write_off_repo: WriteOffRepository = Depends(get_write_off_repository),
        inventory_subject: InventorySubject = Depends(get_inventory_subject)
):
    product = product_repo.get(write_off.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.current_quantity < write_off.quantity:
        raise HTTPException(status_code=400, detail="Not enough quantity in stock")

    total_loss = write_off.quantity * product.purchase_price

    write_off_data = write_off.dict()
    write_off_data["recorded_by"] = current_user.id
    write_off_data["total_loss"] = total_loss

    db_write_off = write_off_repo.create(write_off_data)

    product.current_quantity -= write_off.quantity
    db.commit()

    inventory_subject.notify(
        product_id=write_off.product_id,
        quantity_change=write_off.quantity,
        event_type="write_off"
    )

    return db_write_off


@app.get("/write-offs/", response_model=List[schemas.WriteOff])
def read_write_offs(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    write_offs = db.query(models.WriteOff).offset(skip).limit(limit).all()
    return write_offs


@app.get("/write-offs/{write_off_id}", response_model=schemas.WriteOff)
def read_write_off(
        write_off_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    write_off = db.query(models.WriteOff).filter(models.WriteOff.id == write_off_id).first()
    if not write_off:
        raise HTTPException(status_code=404, detail="Write-off not found")
    return write_off


@app.post("/sales/", response_model=schemas.Sale)
def create_sale(
        sale: schemas.SaleCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    product = db.query(models.Product).filter(models.Product.id == sale.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.current_quantity < sale.quantity_sold:
        raise HTTPException(status_code=400, detail="Not enough quantity in stock")

    sale_data = sale.dict()
    sale_data["recorded_by"] = current_user.id

    db_sale = models.Sale(**sale_data)
    db.add(db_sale)

    product.current_quantity -= sale.quantity_sold
    db.commit()
    db.refresh(db_sale)

    return db_sale


@app.get("/sales/", response_model=List[schemas.Sale])
def read_sales(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    sales = db.query(models.Sale).offset(skip).limit(limit).all()
    return sales


@app.get("/categories/", response_model=List[schemas.Category])
def read_categories(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    categories = db.query(models.Category).offset(skip).limit(limit).all()
    return categories


@app.get("/write-off-reasons/", response_model=List[schemas.WriteOffReason])
def read_write_off_reasons(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    reasons = db.query(models.WriteOffReason).offset(skip).limit(limit).all()
    return reasons


@app.get("/analytics/dashboard", response_model=schemas.AnalyticsResponse)
def get_dashboard_analytics(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    from sqlalchemy import func, desc

    products = db.query(models.Product).all()
    total_products = len(products)
    total_inventory_value = sum(product.current_quantity * product.purchase_price for product in products)

    low_stock_products = sum(1 for product in products if product.current_quantity <= product.min_stock_level)

    total_write_offs = db.query(func.count(models.WriteOff.id)).scalar()
    total_losses = db.query(func.sum(models.WriteOff.total_loss)).scalar() or 0

    total_sales = db.query(func.count(models.Sale.id)).scalar()
    total_revenue = db.query(func.sum(models.Sale.quantity_sold * models.Sale.sale_price)).scalar() or 0

    categories = {}
    for product in products:
        if product.category_rel:
            categories[product.category_rel.name] = categories.get(product.category_rel.name,
                                                                   0) + product.current_quantity

    recent_write_offs = db.query(models.WriteOff).order_by(desc(models.WriteOff.write_off_date)).limit(10).all()
    recent_sales = db.query(models.Sale).order_by(desc(models.Sale.sale_date)).limit(10).all()

    return {
        "total_products": total_products,
        "total_inventory_value": total_inventory_value,
        "low_stock_products": low_stock_products,
        "total_write_offs": total_write_offs,
        "total_losses": total_losses,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "top_categories": categories,
        "recent_write_offs": recent_write_offs,
        "recent_sales": recent_sales
    }


@app.get("/analytics/write-off-report")
def get_write_off_report(
        start_date: datetime,
        end_date: datetime,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_manager())
):
    from sqlalchemy import func

    total_write_offs = db.query(func.count(models.WriteOff.id)).filter(
        models.WriteOff.write_off_date.between(start_date, end_date)
    ).scalar()

    total_quantity = db.query(func.sum(models.WriteOff.quantity)).filter(
        models.WriteOff.write_off_date.between(start_date, end_date)
    ).scalar() or 0

    total_loss = db.query(func.sum(models.WriteOff.total_loss)).filter(
        models.WriteOff.write_off_date.between(start_date, end_date)
    ).scalar() or 0

    write_offs_by_reason = db.query(
        models.WriteOffReason.name,
        func.sum(models.WriteOff.quantity).label('quantity'),
        func.sum(models.WriteOff.total_loss).label('loss')
    ).join(models.WriteOffReason).filter(
        models.WriteOff.write_off_date.between(start_date, end_date)
    ).group_by(models.WriteOffReason.name).all()

    write_offs_by_product = db.query(
        models.Product.name,
        func.sum(models.WriteOff.quantity).label('quantity'),
        func.sum(models.WriteOff.total_loss).label('loss')
    ).join(models.Product).filter(
        models.WriteOff.write_off_date.between(start_date, end_date)
    ).group_by(models.Product.name).all()

    return {
        "period_start": start_date,
        "period_end": end_date,
        "total_write_offs": total_write_offs,
        "total_quantity": total_quantity,
        "total_loss": total_loss,
        "write_offs_by_reason": {row.name: {"quantity": row.quantity, "loss": row.loss} for row in
                                 write_offs_by_reason},
        "write_offs_by_product": [{"name": row.name, "quantity": row.quantity, "loss": row.loss} for row in
                                  write_offs_by_product]
    }


@app.get("/")
def root():
    return {
        "message": "Inventory Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "description": "Система автоматизации учета списания товаров"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}


@app.get("/analytics/inventory-health", response_model=Dict)
def get_inventory_health_report(
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    """Полный отчет о здоровье инвентаря"""
    return analytics.get_inventory_health_report()


@app.get("/analytics/write-offs-detailed")
def get_write_offs_detailed_analytics(
        start_date: datetime,
        end_date: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(get_current_manager())
):
    """Детальная аналитика списаний с использованием Pandas"""
    return analytics.get_write_off_analytics(start_date, end_date)


@app.get("/analytics/sales-detailed")
def get_sales_detailed_analytics(
        start_date: datetime,
        end_date: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(get_current_manager())
):
    """Детальная аналитика продаж с использованием Pandas"""
    return analytics.get_sales_analytics(start_date, end_date)


@app.get("/analytics/comparative")
def get_comparative_analytics(
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(get_current_manager())
):
    """Сравнительная аналитика двух периодов"""
    return analytics.get_comparative_analytics(
        period1_start, period1_end,
        period2_start, period2_end
    )


@app.get("/analytics/write-offs-report/excel")
def download_write_off_report_excel(
        start_date: datetime,
        end_date: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(get_current_manager())
):
    """Скачать Excel отчет по списаниям"""
    try:
        return analytics.generate_write_off_report_excel(start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/analytics/sales-chart")
def get_sales_chart(
        start_date: datetime,
        end_date: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    """Получить график продаж в формате PNG"""
    try:
        image_bytes = analytics.generate_sales_chart(start_date, end_date)
        return Response(content=image_bytes, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/analytics/write-offs-chart")
def get_write_off_chart(
        start_date: datetime,
        end_date: datetime,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    """Получить график списаний в формате PNG"""
    try:
        image_bytes = analytics.generate_write_off_chart(start_date, end_date)
        return Response(content=image_bytes, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/analytics/predictive/{product_id}")
def get_predictive_analytics(
        product_id: int,
        days_ahead: int = 30,
        analytics: InventoryAnalytics = Depends(get_analytics_service),
        current_user: models.User = Depends(get_current_manager())
):
    """Прогнозная аналитика для конкретного товара"""
    from app import models
    from sqlalchemy import func
    from datetime import datetime, timedelta

    db = next(get_db())

    # Получаем историю продаж товара
    sales_history = db.query(models.Sale).filter(
        models.Sale.product_id == product_id,
        models.Sale.sale_date >= datetime.now() - timedelta(days=90)
    ).all()

    # Получаем историю списаний товара
    write_offs_history = db.query(models.WriteOff).filter(
        models.WriteOff.product_id == product_id,
        models.WriteOff.write_off_date >= datetime.now() - timedelta(days=90)
    ).all()

    if not sales_history and not write_offs_history:
        raise HTTPException(status_code=404, detail="Недостаточно данных для анализа")

    # Создаем DataFrame для анализа
    import pandas as pd

    sales_data = []
    for sale in sales_history:
        sales_data.append({
            'date': sale.sale_date.date(),
            'quantity': sale.quantity_sold,
            'type': 'sale'
        })

    write_off_data = []
    for write_off in write_offs_history:
        write_off_data.append({
            'date': write_off.write_off_date.date(),
            'quantity': write_off.quantity,
            'type': 'write_off'
        })

    df_sales = pd.DataFrame(sales_data)
    df_write_offs = pd.DataFrame(write_off_data)

    # Анализ трендов
    result = {
        "product_id": product_id,
        "analysis_period": "90 дней",
        "forecast_days": days_ahead
    }

    if not df_sales.empty:
        # Прогноз продаж (простая линейная регрессия)
        df_sales['date_num'] = (pd.to_datetime(df_sales['date']) - pd.to_datetime(df_sales['date'].min())).dt.days

        if len(df_sales) > 1:
            try:
                z = np.polyfit(df_sales['date_num'], df_sales['quantity'], 1)
                forecast_quantity = z[0] * (df_sales['date_num'].max() + days_ahead) + z[1]
                result["sales_trend"] = {
                    "trend_slope": z[0],
                    "is_increasing": z[0] > 0,
                    "forecast_quantity": max(0, forecast_quantity)
                }
            except:
                result["sales_trend"] = {"error": "Недостаточно данных для прогноза"}

    if not df_write_offs.empty:
        # Анализ списаний
        result["write_offs_summary"] = {
            "total_write_offs": len(df_write_offs),
            "avg_write_off_quantity": df_write_offs['quantity'].mean(),
            "write_off_frequency_days": 90 / len(df_write_offs) if len(df_write_offs) > 0 else None
        }

    # Получаем информацию о текущем запасе
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        result["current_inventory"] = {
            "current_quantity": product.current_quantity,
            "min_stock_level": product.min_stock_level,
            "days_of_supply": (product.current_quantity / df_sales['quantity'].mean())
            if not df_sales.empty and df_sales['quantity'].mean() > 0 else None
        }

    return result