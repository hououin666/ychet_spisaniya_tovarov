from typing import List, Optional, TypeVar, Generic
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class Repository(Generic[ModelType]):

    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ModelType, obj_in: dict) -> ModelType:
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> bool:
        obj = self.db.query(self.model).get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False


class ProductRepository:
    def __init__(self, db: Session):
        from app import models
        self.model = models.Product
        self.db = db

    def get(self, id: int) -> Optional:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj_in: dict):
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj, obj_in: dict):
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> bool:
        obj = self.db.query(self.model).get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

    def get_by_sku(self, sku: str):
        return self.db.query(self.model).filter(self.model.sku == sku).first()

    def get_low_stock(self):
        return self.db.query(self.model).filter(
            self.model.current_quantity <= self.model.min_stock_level
        ).all()


class WriteOffRepository:
    def __init__(self, db: Session):
        from app import models
        self.model = models.WriteOff
        self.db = db

    def get(self, id: int):
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100):
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj_in: dict):
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_product(self, product_id: int):
        return self.db.query(self.model).filter(
            self.model.product_id == product_id
        ).all()