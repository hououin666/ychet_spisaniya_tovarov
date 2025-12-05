from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_active_user
from app import models
from app.analytics import InventoryAnalytics

def get_current_admin():
    def admin_checker(current_user: models.User = Depends(get_current_active_user)):
        if current_user.role != models.UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return current_user
    return admin_checker

def get_current_manager():
    def manager_checker(current_user: models.User = Depends(get_current_active_user)):
        if current_user.role not in [models.UserRole.MANAGER, models.UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager access required"
            )
        return current_user
    return manager_checker

def get_analytics_service(db: Session = Depends(get_db)):
    return InventoryAnalytics(db)