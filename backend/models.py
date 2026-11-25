"""SQLModel кестелері және олардың объектілік байланыстары."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=80)
    slug: str = Field(unique=True, max_length=80)
    products: list["Product"] = Relationship(back_populates="category")


class Product(SQLModel, table=True):
    __table_args__ = (CheckConstraint("price > 0"), CheckConstraint("stock >= 0"))
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=120)
    description: str = Field(max_length=2000)
    price: int
    old_price: Optional[int] = None
    category_id: int = Field(foreign_key="category.id", index=True)
    image_url: str
    stock: int = 20
    occasion: str = "Кез келген күн"
    badge: str = ""
    rating: float = 5.0
    category: Optional[Category] = Relationship(back_populates="products")
    order_items: list["OrderItem"] = Relationship(back_populates="product")


class User(SQLModel, table=True):
    __table_args__ = (CheckConstraint("role IN ('customer', 'admin')"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=80)
    email: str = Field(unique=True, index=True, max_length=254)
    password_hash: str
    role: str = Field(default="customer", max_length=20)
    created_at: datetime = Field(default_factory=utcnow)
    orders: list["Order"] = Relationship(back_populates="user")
    sessions: list["AuthSession"] = Relationship(back_populates="user", cascade_delete=True)


class AuthSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    expires_at: datetime
    user: Optional[User] = Relationship(back_populates="sessions")


class Order(SQLModel, table=True):
    __table_args__ = (CheckConstraint("total >= 0"), CheckConstraint("subtotal >= discount AND discount >= 0"),
                     CheckConstraint("delivery_fee >= 0"), CheckConstraint("total = subtotal - discount + delivery_fee"),
                     CheckConstraint("delivery_method IN ('pickup', 'courier')"),
                     CheckConstraint("status IN ('new', 'confirmed', 'preparing', 'delivering', 'completed', 'cancelled')"))
    id: Optional[int] = Field(default=None, primary_key=True)
    number: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    recipient_name: str
    phone: str
    address: str
    delivery_method: str
    delivery_date: str
    time_slot: str
    card_message: str = ""
    promo_code: str = ""
    subtotal: int
    discount: int
    delivery_fee: int
    total: int
    status: str = "new"
    payment_method: str = "on_delivery"
    created_at: datetime = Field(default_factory=utcnow)
    user: Optional[User] = Relationship(back_populates="orders")
    items: list["OrderItem"] = Relationship(back_populates="order", cascade_delete=True)


class OrderItem(SQLModel, table=True):
    __table_args__ = (CheckConstraint("quantity > 0"), CheckConstraint("unit_price > 0"))
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True, ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id", ondelete="SET NULL")
    product_name: str
    image_url: str
    quantity: int
    unit_price: int
    order: Optional[Order] = Relationship(back_populates="items")
    product: Optional[Product] = Relationship(back_populates="order_items")
