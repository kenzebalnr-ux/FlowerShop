"""Клиент енгізуін деректер қоры модельдерінен бөлек тексеру."""
from datetime import date, timedelta
from typing import Literal
import re
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(InputModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Электрондық пошта дұрыс емес")
        return value

    @field_validator("password")
    @classmethod
    def password_valid(cls, value):
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Құпиясөзде әріп пен сан болуы қажет")
        return value


class Login(InputModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProductCreate(InputModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=2000)
    price: int = Field(gt=0, le=10_000_000, strict=True)
    old_price: int | None = Field(default=None, gt=0, le=10_000_000)
    category_id: int = Field(gt=0)
    image_url: str = Field(default="https://images.unsplash.com/photo-1561181286-d3fee7d55364?w=800&q=85", max_length=1000)
    stock: int = Field(default=20, ge=0, le=100_000, strict=True)
    occasion: str = Field(default="Кез келген күн", max_length=80)
    badge: str = Field(default="", max_length=40)
    rating: float = Field(default=5, ge=0, le=5)

    @field_validator("image_url")
    @classmethod
    def safe_image(cls, value):
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Сурет сілтемесі HTTPS болуы қажет")
        return value


class ProductUpdate(InputModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=5, max_length=2000)
    price: int | None = Field(default=None, gt=0, le=10_000_000, strict=True)
    old_price: int | None = Field(default=None, gt=0, le=10_000_000)
    category_id: int | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=1000)
    stock: int | None = Field(default=None, ge=0, le=100_000, strict=True)
    occasion: str | None = Field(default=None, max_length=80)
    badge: str | None = Field(default=None, max_length=40)
    rating: float | None = Field(default=None, ge=0, le=5)

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set if field != "old_price"):
            raise ValueError("Міндетті өрістерге бос мән жіберуге болмайды")
        if self.image_url is not None:
            ProductCreate.safe_image(self.image_url)
        return self


class CartItem(InputModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=20, strict=True)


class OrderCreate(InputModel):
    items: list[CartItem] = Field(min_length=1, max_length=30)
    recipient_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=30)
    address: str = Field(default="", max_length=500)
    delivery_method: Literal["courier", "pickup"] = "courier"
    delivery_date: date
    time_slot: str = Field(default="Кез келген уақытта", max_length=80)
    card_message: str = Field(default="", max_length=500)
    promo_code: str = Field(default="", max_length=30)
    payment_method: Literal["on_delivery"] = "on_delivery"

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        digits = re.sub(r"[\s()+-]", "", value)
        if not digits.isdigit() or not 10 <= len(digits) <= 15:
            raise ValueError("Телефон нөмірі дұрыс емес")
        return value

    @model_validator(mode="after")
    def validate_order(self):
        if self.delivery_method == "courier" and len(self.address) < 5:
            raise ValueError("Жеткізу мекенжайын толық енгізіңіз")
        # Date in Kazakhstan, independent of the server's UTC/local timezone.
        from datetime import datetime, timezone
        today = datetime.now(timezone(timedelta(hours=5))).date()
        if not today <= self.delivery_date <= today + timedelta(days=60):
            raise ValueError("Жеткізу күні бүгіннен бастап 60 күн ішінде болуы қажет")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Себетте қайталанатын тауар бар")
        self.promo_code = self.promo_code.upper()
        if self.promo_code not in ("", "GUL10"):
            raise ValueError("Промокод табылмады")
        return self


class StatusUpdate(InputModel):
    status: Literal["new", "confirmed", "preparing", "delivering", "completed", "cancelled"]
