from abc import ABC, abstractmethod
from typing import List


class InventoryObserver(ABC):
    @abstractmethod
    def update(self, product_id: int, quantity_change: int, event_type: str):
        pass


class LowStockNotifier(InventoryObserver):
    def __init__(self, db):
        self.db = db

    def update(self, product_id: int, quantity_change: int, event_type: str):
        from app import models
        product = self.db.query(models.Product).filter(models.Product.id == product_id).first()
        if product and product.current_quantity <= product.min_stock_level:
            print(f"ALERT: Low stock for product {product.name}. Current quantity: {product.current_quantity}")


class LossAnalyticsObserver(InventoryObserver):
    def __init__(self, db):
        self.db = db

    def update(self, product_id: int, quantity_change: int, event_type: str):
        if event_type == "write_off":
            from app import models
            product = self.db.query(models.Product).filter(models.Product.id == product_id).first()
            if product:
                loss_amount = quantity_change * product.purchase_price
                print(f"Loss recorded: ${loss_amount:.2f} for product {product.name}")


class InventorySubject:
    def __init__(self):
        self._observers: List[InventoryObserver] = []

    def attach(self, observer: InventoryObserver):
        self._observers.append(observer)

    def detach(self, observer: InventoryObserver):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, product_id: int, quantity_change: int, event_type: str):
        for observer in self._observers:
            observer.update(product_id, quantity_change, event_type)