from app.main import app
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("Inventory Management System")
    print("Система учета списания товаров")
    print("=" * 50)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )