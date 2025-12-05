import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import io
from fastapi.responses import StreamingResponse
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

matplotlib.use('Agg')  # Для работы без GUI
import json

from app import models


class NumpyEncoder(json.JSONEncoder):
    """Кастомный JSON encoder для обработки NumPy типов"""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)


def convert_numpy_types(obj: Any) -> Any:
    """Рекурсивно конвертирует NumPy типы в стандартные Python типы"""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, pd.Series):
        return convert_numpy_types(obj.to_dict())
    elif isinstance(obj, pd.DataFrame):
        return convert_numpy_types(obj.to_dict('records'))
    else:
        return obj


class InventoryAnalytics:
    def __init__(self, db: Session):
        self.db = db

    def _get_products_dataframe(self) -> pd.DataFrame:
        """Получение данных о товарах в DataFrame"""
        products = self.db.query(models.Product).all()

        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category': product.category_rel.name if product.category_rel else 'Не указана',
                'supplier': product.supplier_rel.name if product.supplier_rel else 'Не указан',
                'purchase_price': float(product.purchase_price),
                'selling_price': float(product.selling_price),
                'current_quantity': int(product.current_quantity),
                'min_stock_level': int(product.min_stock_level),
                'inventory_value': float(product.current_quantity * product.purchase_price),
                'profit_margin': float(((product.selling_price - product.purchase_price) / product.purchase_price * 100)
                                       if product.purchase_price > 0 else 0),
                'days_since_update': int((datetime.now() - product.updated_at.replace(tzinfo=None)).days
                                         if product.updated_at else 0)
            })

        return pd.DataFrame(data)

    def _get_write_offs_dataframe(self, start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Получение данных о списаниях в DataFrame"""
        query = self.db.query(models.WriteOff)

        if start_date and end_date:
            query = query.filter(models.WriteOff.write_off_date.between(start_date, end_date))

        write_offs = query.all()

        data = []
        for write_off in write_offs:
            data.append({
                'id': int(write_off.id),
                'product_id': int(write_off.product_id),
                'product_name': write_off.product.name,
                'quantity': int(write_off.quantity),
                'reason': write_off.reason.name,
                'total_loss': float(write_off.total_loss),
                'write_off_date': write_off.write_off_date,
                'recorded_by': write_off.recorded_by_user.full_name if write_off.recorded_by_user else 'Неизвестно',
                'notes': write_off.notes
            })

        return pd.DataFrame(data) if data else pd.DataFrame()

    def _get_sales_dataframe(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Получение данных о продажах в DataFrame"""
        query = self.db.query(models.Sale)

        if start_date and end_date:
            query = query.filter(models.Sale.sale_date.between(start_date, end_date))

        sales = query.all()

        data = []
        for sale in sales:
            data.append({
                'id': int(sale.id),
                'product_id': int(sale.product_id),
                'product_name': sale.product.name,
                'quantity_sold': int(sale.quantity_sold),
                'sale_price': float(sale.sale_price),
                'total_revenue': float(sale.quantity_sold * sale.sale_price),
                'cost_price': float(sale.product.purchase_price),
                'total_cost': float(sale.quantity_sold * sale.product.purchase_price),
                'profit': float(
                    (sale.quantity_sold * sale.sale_price) - (sale.quantity_sold * sale.product.purchase_price)),
                'sale_date': sale.sale_date,
                'recorded_by': sale.recorded_by_user.full_name if sale.recorded_by_user else 'Неизвестно',
                'customer_info': sale.customer_info
            })

        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_inventory_health_report(self) -> Dict:
        """Отчет о здоровье инвентаря"""
        df_products = self._get_products_dataframe()

        if df_products.empty:
            return {"error": "Нет данных о товарах"}

        # Преобразуем все NumPy типы
        df_products = df_products.copy()
        for col in df_products.select_dtypes(include=[np.number]).columns:
            df_products[col] = df_products[col].astype(float)

        # Анализ запасов
        low_stock_products = df_products[df_products['current_quantity'] <= df_products['min_stock_level']]
        out_of_stock_products = df_products[df_products['current_quantity'] == 0]
        overstock_products = df_products[df_products['current_quantity'] > df_products['min_stock_level'] * 3]
        optimal_stock_products = df_products[
            (df_products['current_quantity'] > df_products['min_stock_level']) &
            (df_products['current_quantity'] <= df_products['min_stock_level'] * 3)
            ]

        # Анализ по категориям
        category_analysis = {}
        for category, group in df_products.groupby('category'):
            category_analysis[category] = {
                'inventory_value': float(group['inventory_value'].sum()),
                'total_quantity': int(group['current_quantity'].sum()),
                'avg_profit_margin': float(group['profit_margin'].mean()) if not group.empty else 0.0
            }

        # Топ товаров
        top_products_by_value = []
        if not df_products.empty:
            top_products = df_products.nlargest(10, 'inventory_value')
            for _, row in top_products.iterrows():
                top_products_by_value.append({
                    'name': str(row['name']),
                    'inventory_value': float(row['inventory_value'])
                })

        low_profit_products = []
        if not df_products.empty:
            low_profit = df_products.nsmallest(10, 'profit_margin')
            for _, row in low_profit.iterrows():
                low_profit_products.append({
                    'name': str(row['name']),
                    'profit_margin': float(row['profit_margin'])
                })

        report = {
            "total_products": int(len(df_products)),
            "total_inventory_value": float(df_products['inventory_value'].sum()),
            "average_profit_margin": float(df_products['profit_margin'].mean()) if not df_products.empty else 0.0,

            "stock_analysis": {
                "low_stock_count": int(len(low_stock_products)),
                "out_of_stock_count": int(len(out_of_stock_products)),
                "overstock_count": int(len(overstock_products)),
                "optimal_stock_count": int(len(optimal_stock_products))
            },

            "category_analysis": category_analysis,
            "top_products_by_value": top_products_by_value,
            "low_profit_products": low_profit_products,

            "summary_statistics": {
                "avg_quantity": float(df_products['current_quantity'].mean()) if not df_products.empty else 0.0,
                "std_quantity": float(df_products['current_quantity'].std()) if len(df_products) > 1 else 0.0,
                "avg_price": float(df_products['purchase_price'].mean()) if not df_products.empty else 0.0,
                "price_range": {
                    "min": float(df_products['purchase_price'].min()) if not df_products.empty else 0.0,
                    "max": float(df_products['purchase_price'].max()) if not df_products.empty else 0.0
                }
            }
        }

        return convert_numpy_types(report)

    def get_write_off_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Аналитика списаний за период"""
        df_write_offs = self._get_write_offs_dataframe(start_date, end_date)

        if df_write_offs.empty:
            return {"error": "Нет данных о списаниях за указанный период"}

        # Преобразуем NumPy типы
        df_write_offs = df_write_offs.copy()
        for col in df_write_offs.select_dtypes(include=[np.number]).columns:
            df_write_offs[col] = df_write_offs[col].astype(float)

        # Анализ по причинам
        reason_analysis = {}
        if 'reason' in df_write_offs.columns and not df_write_offs.empty:
            for reason, group in df_write_offs.groupby('reason'):
                reason_analysis[reason] = {
                    'quantity': int(group['quantity'].sum()),
                    'total_loss': float(group['total_loss'].sum()),
                    'count': int(len(group))
                }

        # Анализ по продуктам
        product_analysis = {}
        if not df_write_offs.empty:
            product_groups = df_write_offs.groupby('product_name').agg({
                'quantity': 'sum',
                'total_loss': 'sum'
            })
            # Берем топ 10
            top_products = product_groups.nlargest(10, 'total_loss')
            for product_name, row in top_products.iterrows():
                product_analysis[str(product_name)] = {
                    'quantity': int(row['quantity']),
                    'total_loss': float(row['total_loss'])
                }

        # Временной анализ
        daily_analysis = {}
        if not df_write_offs.empty and 'write_off_date' in df_write_offs.columns:
            df_write_offs['date'] = pd.to_datetime(df_write_offs['write_off_date']).dt.date
            for date_val, group in df_write_offs.groupby('date'):
                daily_analysis[str(date_val)] = {
                    'quantity': int(group['quantity'].sum()),
                    'total_loss': float(group['total_loss'].sum())
                }

        # Статистика
        stats = {
            "total_write_offs": int(len(df_write_offs)),
            "total_quantity_lost": int(df_write_offs['quantity'].sum()) if not df_write_offs.empty else 0,
            "total_financial_loss": float(df_write_offs['total_loss'].sum()) if not df_write_offs.empty else 0.0,
            "avg_loss_per_write_off": float(df_write_offs['total_loss'].mean()) if not df_write_offs.empty else 0.0,
            "max_single_loss": float(df_write_offs['total_loss'].max()) if not df_write_offs.empty else 0.0
        }

        # Определяем самую частую причину
        if not df_write_offs.empty and 'reason' in df_write_offs.columns:
            most_common = df_write_offs['reason'].mode()
            if not most_common.empty:
                stats["most_common_reason"] = str(most_common.iloc[0])

        # Топ списаний
        top_write_offs = []
        if not df_write_offs.empty:
            top_df = df_write_offs.nlargest(10, 'total_loss')
            for _, row in top_df.iterrows():
                top_write_offs.append({
                    'product_name': str(row['product_name']),
                    'quantity': int(row['quantity']),
                    'total_loss': float(row['total_loss']),
                    'reason': str(row['reason'])
                })

        result = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "statistics": stats,
            "reason_analysis": reason_analysis,
            "product_analysis": product_analysis,
            "daily_analysis": daily_analysis,
            "top_write_offs": top_write_offs
        }

        return convert_numpy_types(result)

    def get_sales_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Аналитика продаж за период"""
        df_sales = self._get_sales_dataframe(start_date, end_date)

        if df_sales.empty:
            return {"error": "Нет данных о продажах за указанный период"}

        # Преобразуем NumPy типы
        df_sales = df_sales.copy()
        for col in df_sales.select_dtypes(include=[np.number]).columns:
            df_sales[col] = df_sales[col].astype(float)

        # Общая статистика
        stats = {
            "total_sales": int(len(df_sales)),
            "total_quantity_sold": int(df_sales['quantity_sold'].sum()) if not df_sales.empty else 0,
            "total_revenue": float(df_sales['total_revenue'].sum()) if not df_sales.empty else 0.0,
            "total_cost": float(df_sales['total_cost'].sum()) if not df_sales.empty else 0.0,
            "total_profit": float(df_sales['profit'].sum()) if not df_sales.empty else 0.0,
            "avg_sale_value": float(df_sales['total_revenue'].mean()) if not df_sales.empty else 0.0
        }

        if stats["total_cost"] > 0:
            stats["avg_profit_margin"] = float((stats["total_profit"] / stats["total_cost"]) * 100)

        # Лучший день продаж
        if not df_sales.empty:
            df_sales['date'] = pd.to_datetime(df_sales['sale_date']).dt.date
            daily_revenue = df_sales.groupby('date')['total_revenue'].sum()
            if not daily_revenue.empty:
                best_day = daily_revenue.idxmax()
                stats["best_selling_day"] = str(best_day)
                stats["best_day_revenue"] = float(daily_revenue.max())

        # Анализ по продуктам
        product_analysis = {}
        if not df_sales.empty:
            product_groups = df_sales.groupby('product_name').agg({
                'quantity_sold': 'sum',
                'total_revenue': 'sum',
                'profit': 'sum'
            })
            # Топ 10 продуктов
            top_products = product_groups.nlargest(10, 'total_revenue')
            for product_name, row in top_products.iterrows():
                product_analysis[str(product_name)] = {
                    'quantity_sold': int(row['quantity_sold']),
                    'total_revenue': float(row['total_revenue']),
                    'profit': float(row['profit'])
                }

        # Временной анализ
        daily_analysis = {}
        weekday_analysis = {}
        hourly_analysis = {}

        if not df_sales.empty:
            # Ежедневный анализ
            for date_val, group in df_sales.groupby('date'):
                daily_analysis[str(date_val)] = {
                    'quantity_sold': int(group['quantity_sold'].sum()),
                    'total_revenue': float(group['total_revenue'].sum()),
                    'profit': float(group['profit'].sum())
                }

            # Анализ по дням недели
            df_sales['day_of_week'] = pd.to_datetime(df_sales['sale_date']).dt.day_name()
            for day, group in df_sales.groupby('day_of_week'):
                weekday_analysis[str(day)] = {
                    'total_revenue': float(group['total_revenue'].sum()),
                    'profit': float(group['profit'].sum())
                }

            # Анализ по часам
            df_sales['hour'] = pd.to_datetime(df_sales['sale_date']).dt.hour
            for hour, group in df_sales.groupby('hour'):
                hourly_analysis[str(int(hour))] = {
                    'total_revenue': float(group['total_revenue'].sum())
                }

        # ABC анализ
        abc_analysis = []
        if not df_sales.empty:
            df_abc = df_sales.groupby('product_name').agg({
                'total_revenue': 'sum'
            }).sort_values('total_revenue', ascending=False)

            df_abc['cumulative_percentage'] = df_abc['total_revenue'].cumsum() / df_abc['total_revenue'].sum() * 100
            df_abc['category'] = pd.cut(
                df_abc['cumulative_percentage'],
                bins=[0, 80, 95, 100],
                labels=['A', 'B', 'C']
            )

            for product_name, row in df_abc.iterrows():
                abc_analysis.append({
                    'product_name': str(product_name),
                    'total_revenue': float(row['total_revenue']),
                    'cumulative_percentage': float(row['cumulative_percentage']),
                    'category': str(row['category'])
                })

        # Топ продаж
        top_sales = []
        if not df_sales.empty:
            top_df = df_sales.nlargest(10, 'total_revenue')
            for _, row in top_df.iterrows():
                top_sales.append({
                    'product_name': str(row['product_name']),
                    'quantity_sold': int(row['quantity_sold']),
                    'total_revenue': float(row['total_revenue']),
                    'profit': float(row['profit'])
                })

        result = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "statistics": stats,
            "product_analysis": product_analysis,
            "daily_analysis": daily_analysis,
            "weekday_analysis": weekday_analysis,
            "hourly_analysis": hourly_analysis,
            "abc_analysis": abc_analysis,
            "top_sales": top_sales
        }

        return convert_numpy_types(result)

    def get_comparative_analytics(self, period1_start: datetime, period1_end: datetime,
                                  period2_start: datetime, period2_end: datetime) -> Dict:
        """Сравнительная аналитика двух периодов"""
        # Получаем данные для двух периодов
        df_sales_period1 = self._get_sales_dataframe(period1_start, period1_end)
        df_sales_period2 = self._get_sales_dataframe(period2_start, period2_end)

        df_write_offs_period1 = self._get_write_offs_dataframe(period1_start, period1_end)
        df_write_offs_period2 = self._get_write_offs_dataframe(period2_start, period2_end)

        # Вычисляем показатели
        period1_revenue = float(df_sales_period1['total_revenue'].sum()) if not df_sales_period1.empty else 0.0
        period2_revenue = float(df_sales_period2['total_revenue'].sum()) if not df_sales_period2.empty else 0.0

        period1_profit = float(df_sales_period1['profit'].sum()) if not df_sales_period1.empty else 0.0
        period2_profit = float(df_sales_period2['profit'].sum()) if not df_sales_period2.empty else 0.0

        period1_loss = float(df_write_offs_period1['total_loss'].sum()) if not df_write_offs_period1.empty else 0.0
        period2_loss = float(df_write_offs_period2['total_loss'].sum()) if not df_write_offs_period2.empty else 0.0

        # Вычисляем изменения
        revenue_change = 0.0
        if period1_revenue > 0:
            revenue_change = float((period2_revenue - period1_revenue) / period1_revenue * 100)

        profit_change = 0.0
        if period1_profit > 0:
            profit_change = float((period2_profit - period1_profit) / period1_profit * 100)

        loss_change = 0.0
        if period1_loss > 0:
            loss_change = float((period2_loss - period1_loss) / period1_loss * 100)

        comparison = {
            "periods": {
                "period1": {
                    "start": period1_start.isoformat(),
                    "end": period1_end.isoformat()
                },
                "period2": {
                    "start": period2_start.isoformat(),
                    "end": period2_end.isoformat()
                }
            },
            "sales_comparison": {
                "period1_revenue": period1_revenue,
                "period2_revenue": period2_revenue,
                "revenue_change": revenue_change,
                "period1_profit": period1_profit,
                "period2_profit": period2_profit,
                "profit_change": profit_change
            },
            "write_offs_comparison": {
                "period1_loss": period1_loss,
                "period2_loss": period2_loss,
                "loss_change": loss_change
            }
        }

        return comparison

    def generate_write_off_report_excel(self, start_date: datetime, end_date: datetime) -> StreamingResponse:
        """Генерация Excel отчета по списаниям"""
        df_write_offs = self._get_write_offs_dataframe(start_date, end_date)
        df_products = self._get_products_dataframe()

        if df_write_offs.empty:
            raise ValueError("Нет данных о списаниях за указанный период")

        # Преобразуем NumPy типы в стандартные Python типы
        df_write_offs = df_write_offs.copy()
        for col in df_write_offs.select_dtypes(include=[np.number]).columns:
            df_write_offs[col] = df_write_offs[col].astype(float)

        df_products = df_products.copy()
        for col in df_products.select_dtypes(include=[np.number]).columns:
            df_products[col] = df_products[col].astype(float)

        # Создаем Excel writer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Лист с детализацией списаний
            df_write_offs.to_excel(writer, sheet_name='Детализация списаний', index=False)

            # Лист с анализом по причинам
            if not df_write_offs.empty and 'reason' in df_write_offs.columns:
                reason_analysis = df_write_offs.groupby('reason').agg({
                    'quantity': 'sum',
                    'total_loss': 'sum'
                })
                reason_analysis['количество_списаний'] = df_write_offs.groupby('reason').size()
                reason_analysis = reason_analysis.astype(float)
                reason_analysis.to_excel(writer, sheet_name='Анализ по причинам')

            # Лист с анализом по продуктам
            if not df_write_offs.empty and 'product_name' in df_write_offs.columns:
                product_analysis = df_write_offs.groupby('product_name').agg({
                    'quantity': 'sum',
                    'total_loss': 'sum'
                }).sort_values('total_loss', ascending=False)
                product_analysis = product_analysis.astype(float)
                product_analysis.to_excel(writer, sheet_name='Анализ по продуктам')

            # Лист со статистикой
            stats_data = []
            stats_data.append(['Показатель', 'Значение'])
            stats_data.append(['Общее количество списаний', len(df_write_offs)])
            stats_data.append(['Общее количество списанных единиц', int(df_write_offs['quantity'].sum())])
            stats_data.append(['Общий финансовый ущерб', float(df_write_offs['total_loss'].sum())])
            stats_data.append(['Средний ущерб на одно списание', float(df_write_offs['total_loss'].mean())])
            stats_data.append(['Максимальный ущерб от одного списания', float(df_write_offs['total_loss'].max())])

            if not df_write_offs.empty and 'reason' in df_write_offs.columns:
                most_common = df_write_offs['reason'].mode()
                if not most_common.empty:
                    stats_data.append(['Наиболее частая причина списания', str(most_common.iloc[0])])

            stats_df = pd.DataFrame(stats_data[1:], columns=stats_data[0])
            stats_df.to_excel(writer, sheet_name='Статистика', index=False)

            # Лист с товарами под риском
            if not df_products.empty:
                risk_products = df_products[df_products['current_quantity'] <= df_products['min_stock_level']]
                if not risk_products.empty:
                    risk_cols = ['name', 'sku', 'category', 'current_quantity', 'min_stock_level', 'inventory_value']
                    available_cols = [col for col in risk_cols if col in risk_products.columns]
                    risk_products[available_cols].to_excel(
                        writer, sheet_name='Товары под риском', index=False
                    )

        output.seek(0)

        filename = f"write_off_report_{start_date.date()}_to_{end_date.date()}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    def generate_sales_chart(self, start_date: datetime, end_date: datetime) -> bytes:
        """Генерация графика продаж"""
        df_sales = self._get_sales_dataframe(start_date, end_date)

        if df_sales.empty:
            raise ValueError("Нет данных о продажах за указанный период")

        # Создаем график
        plt.figure(figsize=(12, 6))

        # График ежедневной выручки
        df_sales['date'] = pd.to_datetime(df_sales['sale_date']).dt.date
        daily_revenue = df_sales.groupby('date')['total_revenue'].sum()

        plt.subplot(1, 2, 1)
        daily_revenue.plot(kind='line', marker='o', color='blue')
        plt.title('Ежедневная выручка')
        plt.xlabel('Дата')
        plt.ylabel('Выручка')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)

        # График топ продуктов
        plt.subplot(1, 2, 2)
        top_products = df_sales.groupby('product_name')['total_revenue'].sum().nlargest(10)
        top_products.plot(kind='bar', color='green')
        plt.title('Топ 10 продуктов по выручке')
        plt.xlabel('Продукт')
        plt.ylabel('Выручка')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        # Сохраняем в bytes
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer.getvalue()

    def generate_write_off_chart(self, start_date: datetime, end_date: datetime) -> bytes:
        """Генерация графика списаний"""
        df_write_offs = self._get_write_offs_dataframe(start_date, end_date)

        if df_write_offs.empty:
            raise ValueError("Нет данных о списаниях за указанный период")

        # Создаем график
        plt.figure(figsize=(12, 6))

        # График по причинам списаний
        plt.subplot(1, 2, 1)
        if not df_write_offs.empty and 'reason' in df_write_offs.columns:
            reason_loss = df_write_offs.groupby('reason')['total_loss'].sum()
            if not reason_loss.empty:
                reason_loss.plot(kind='pie', autopct='%1.1f%%', startangle=90)
                plt.title('Распределение ущерба по причинам списания')
                plt.ylabel('')

        # График временного тренда
        plt.subplot(1, 2, 2)
        if not df_write_offs.empty and 'write_off_date' in df_write_offs.columns:
            df_write_offs['date'] = pd.to_datetime(df_write_offs['write_off_date']).dt.date
            daily_loss = df_write_offs.groupby('date')['total_loss'].sum()
            if not daily_loss.empty:
                daily_loss.plot(kind='bar', color='red', alpha=0.7)
                plt.title('Ежедневный ущерб от списаний')
                plt.xlabel('Дата')
                plt.ylabel('Ущерб')
                plt.xticks(rotation=45)
                plt.grid(True, alpha=0.3)

        plt.tight_layout()

        # Сохраняем в bytes
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer.getvalue()