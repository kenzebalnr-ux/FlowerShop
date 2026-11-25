"""FlowerShop REST API және қазақша дүкен интерфейсі."""
from collections import defaultdict, deque
from pathlib import Path
import secrets
import time
from threading import Lock

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .db import get_session, init_db, make_engine
from .models import AuthSession, Category, Order, OrderItem, Product, User
from .schemas import Login, OrderCreate, ProductCreate, ProductUpdate, Register, StatusUpdate
from .security import (bearer, current_user, hash_password, issue_session, public_user,
                       require_admin, token_digest, verify_password)
from .seed import seed_database

STATIC = Path(__file__).resolve().parents[1] / "frontend" / "static"


def calculate_totals(subtotal: int, delivery_method: str, promo_code: str = "") -> dict:
    """Барлық есеп бүтін теңгемен орындалады; клиент сомасына сенім жоқ."""
    if not isinstance(subtotal, int) or isinstance(subtotal, bool) or subtotal < 0:
        raise ValueError("Сома теріс болмауы қажет")
    if delivery_method not in ("pickup", "courier") or promo_code not in ("", "GUL10"):
        raise ValueError("Жеткізу тәсілі немесе промокод дұрыс емес")
    discount = subtotal // 10 if promo_code == "GUL10" else 0
    fee = 0 if delivery_method == "pickup" or subtotal - discount >= 25000 else 1500
    return {"subtotal": subtotal, "discount": discount, "delivery_fee": fee,
            "total": subtotal - discount + fee}


def order_dict(session: Session, order: Order) -> dict:
    result = order.model_dump()
    result["items"] = [item.model_dump() for item in session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)).all()]
    return result


def create_app(database_url: str | None = None, seed: bool = True) -> FastAPI:
    application = FastAPI(title="FlowerShop — гүлдерге онлайн тапсырыс", version="1.0.0",
                          description="Қазақша интернет-дүкеннің REST API құжаттамасы.")
    api = APIRouter(prefix="/api")
    engine = make_engine(database_url)
    application.state.engine = engine
    init_db(engine)
    if seed:
        seed_database(engine)
    attempts = defaultdict(deque)
    attempts_lock = Lock()

    @application.middleware("http")
    async def secure_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/api/auth") or request.url.path.startswith("/api/orders"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        # The original lab uses FastAPI's 422; lab 8 asks for a uniform 400 contract.
        fields = [".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()]
        return JSONResponse(status_code=400, content={
            "detail": "Енгізілген деректерді тексеріңіз. Міндетті өрістерді дұрыс толтырыңыз.",
            "fields": fields})

    @application.exception_handler(IntegrityError)
    async def integrity_error(_request, _exc):
        return JSONResponse(status_code=409, content={"detail": "Деректер қайшылығы. Өзгерістер сақталмады."})

    @api.get("/health", tags=["Жүйе"])
    def health():
        with Session(engine) as session:
            session.exec(select(Category).limit(1)).first()
        return {"status": "ok", "service": "FlowerShop"}

    @api.get("/categories", tags=["Каталог"])
    def categories(session: Session = Depends(get_session)):
        return session.exec(select(Category).order_by(Category.id)).all()

    @api.get("/products", tags=["Каталог"])
    def products(search: str = Query(default="", max_length=120), category_id: int | None = None,
                 min_price: int | None = Query(default=None, ge=0),
                 max_price: int | None = Query(default=None, ge=0),
                 sort: str = "popular", limit: int = Query(default=100, ge=1, le=200),
                 offset: int = Query(default=0, ge=0), session: Session = Depends(get_session)):
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(400, "Ең төменгі баға ең жоғарғы бағадан аспауы қажет.")
        query = select(Product)
        if search.strip():
            # SQL parameters prevent injection. SQLite lower() is overridden with Unicode casefold.
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(Product.name.ilike(f"%{escaped}%", escape="\\"))
        if category_id is not None:
            query = query.where(Product.category_id == category_id)
        if min_price is not None:
            query = query.where(Product.price >= min_price)
        if max_price is not None:
            query = query.where(Product.price <= max_price)
        sorting = {"popular": Product.id.asc(), "price_asc": Product.price.asc(),
                   "price_desc": Product.price.desc(), "new": Product.id.desc()}
        if sort not in sorting:
            raise HTTPException(400, "Сұрыптау тәсілі дұрыс емес.")
        return session.exec(query.order_by(sorting[sort])
                            .offset(offset).limit(limit)).all()

    def find_product(session, product_id):
        product = session.get(Product, product_id)
        if product is None:
            raise HTTPException(404, "Гүлшоғы табылмады.")
        return product

    @api.get("/products/{product_id}", tags=["Каталог"])
    def product_detail(product_id: int, session: Session = Depends(get_session)):
        return find_product(session, product_id)

    @api.post("/products", status_code=201, tags=["Әкімші"])
    def add_product(data: ProductCreate, _user: User = Depends(require_admin),
                    session: Session = Depends(get_session)):
        if session.get(Category, data.category_id) is None:
            raise HTTPException(404, "Санат табылмады.")
        product = Product(**data.model_dump())
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    def update_product(product_id, values, session):
        product = find_product(session, product_id)
        if "category_id" in values and session.get(Category, values["category_id"]) is None:
            raise HTTPException(404, "Санат табылмады.")
        product.sqlmodel_update(values)
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    @api.patch("/products/{product_id}", tags=["Әкімші"])
    def patch_product(product_id: int, data: ProductUpdate, _user: User = Depends(require_admin),
                      session: Session = Depends(get_session)):
        return update_product(product_id, data.model_dump(exclude_unset=True), session)

    @api.put("/products/{product_id}", tags=["Әкімші"])
    def put_product(product_id: int, data: ProductCreate, _user: User = Depends(require_admin),
                    session: Session = Depends(get_session)):
        return update_product(product_id, data.model_dump(), session)

    @api.delete("/products/{product_id}", status_code=204, tags=["Әкімші"])
    def delete_product(product_id: int, _user: User = Depends(require_admin),
                       session: Session = Depends(get_session)):
        product = find_product(session, product_id)
        session.delete(product)
        session.commit()
        return Response(status_code=204)

    def throttle(request: Request):
        address = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with attempts_lock:
            bucket = attempts[address]
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= 20:
                raise HTTPException(429, "Сұраныс тым көп. Бір минуттан кейін қайталаңыз.", headers={"Retry-After": "60"})
            bucket.append(now)
            if len(attempts) > 10000:
                for key in list(attempts):
                    if not attempts[key] or now - attempts[key][-1] > 60:
                        del attempts[key]

    @api.post("/auth/register", status_code=201, tags=["Аккаунт"])
    def register(data: Register, request: Request, session: Session = Depends(get_session)):
        throttle(request)
        if session.exec(select(User).where(User.email == data.email)).first():
            raise HTTPException(409, "Бұл электрондық пошта тіркелген.")
        user = User(name=data.name, email=data.email, password_hash=hash_password(data.password))
        session.add(user)
        session.commit()
        session.refresh(user)
        return issue_session(session, user)

    @api.post("/auth/login", tags=["Аккаунт"])
    def login(data: Login, request: Request, session: Session = Depends(get_session)):
        throttle(request)
        user = session.exec(select(User).where(User.email == data.email.lower())).first()
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(401, "Электрондық пошта немесе құпиясөз қате.")
        return issue_session(session, user)

    @api.get("/auth/me", tags=["Аккаунт"])
    def me(user: User = Depends(current_user)):
        return public_user(user)

    @api.post("/auth/logout", status_code=204, tags=["Аккаунт"])
    def logout(credentials=Depends(bearer), _user: User = Depends(current_user),
               session: Session = Depends(get_session)):
        auth = session.exec(select(AuthSession).where(AuthSession.token_hash == token_digest(credentials.credentials))).first()
        if auth:
            session.delete(auth)
            session.commit()
        return Response(status_code=204)

    @api.post("/orders", status_code=201, tags=["Тапсырыстар"])
    def create_order(data: OrderCreate, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
        basket = []
        try:
            for item in data.items:
                product = find_product(session, item.product_id)
                result = session.execute(update(Product).where(Product.id == item.product_id,
                    Product.stock >= item.quantity).values(stock=Product.stock - item.quantity))
                if result.rowcount != 1:
                    raise HTTPException(409, f"«{product.name}» гүлшоғының саны жеткіліксіз.")
                basket.append((product, item.quantity))
            totals = calculate_totals(sum(product.price * qty for product, qty in basket),
                                      data.delivery_method, data.promo_code)
            order = Order(number=f"FS-{secrets.token_hex(4).upper()}", user_id=user.id,
                          **data.model_dump(exclude={"items", "delivery_date"}),
                          delivery_date=data.delivery_date.isoformat(), **totals)
            session.add(order)
            session.flush()
            for product, quantity in basket:
                session.add(OrderItem(order_id=order.id, product_id=product.id,
                    product_name=product.name, image_url=product.image_url,
                    quantity=quantity, unit_price=product.price))
            session.commit()
            session.refresh(order)
            return order_dict(session, order)
        except Exception:
            session.rollback()
            raise

    @api.get("/orders", tags=["Тапсырыстар"])
    def my_orders(user: User = Depends(current_user), session: Session = Depends(get_session)):
        return [order_dict(session, order) for order in session.exec(
            select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())).all()]

    @api.get("/orders/{order_id}", tags=["Тапсырыстар"])
    def order_detail(order_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
        order = session.get(Order, order_id)
        if order is None or (order.user_id != user.id and user.role != "admin"):
            raise HTTPException(404, "Тапсырыс табылмады.")
        return order_dict(session, order)

    @api.get("/admin/orders", tags=["Әкімші"])
    def all_orders(_user: User = Depends(require_admin), session: Session = Depends(get_session)):
        return [order_dict(session, order) for order in session.exec(select(Order).order_by(Order.id.desc())).all()]

    @api.patch("/admin/orders/{order_id}", tags=["Әкімші"])
    def set_status(order_id: int, data: StatusUpdate, _user: User = Depends(require_admin),
                   session: Session = Depends(get_session)):
        order = session.get(Order, order_id)
        if order is None:
            raise HTTPException(404, "Тапсырыс табылмады.")
        allowed = {"new": {"confirmed", "cancelled"}, "confirmed": {"preparing", "cancelled"},
                   "preparing": {"delivering", "completed", "cancelled"}, "delivering": {"completed"},
                   "completed": set(), "cancelled": set()}
        if data.status != order.status and data.status not in allowed.get(order.status, set()):
            raise HTTPException(409, "Тапсырыс күйін бұл тәртіппен өзгертуге болмайды.")
        previous_status = order.status
        changed = session.execute(update(Order).where(Order.id == order.id, Order.status == previous_status)
                                  .values(status=data.status))
        if changed.rowcount != 1:
            session.rollback()
            raise HTTPException(409, "Тапсырыс күйі өзгерді. Бетті жаңартып қайталаңыз.")
        if data.status == "cancelled" and previous_status != "cancelled":
            for item in session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all():
                if item.product_id:
                    session.execute(update(Product).where(Product.id == item.product_id)
                                    .values(stock=Product.stock + item.quantity))
        session.commit()
        session.refresh(order)
        return order_dict(session, order)

    @api.get("/admin/stats", tags=["Әкімші"])
    def admin_stats(_user: User = Depends(require_admin), session: Session = Depends(get_session)):
        return {"products": session.exec(select(func.count(Product.id))).one(),
                "orders": session.exec(select(func.count(Order.id))).one(),
                "customers": session.exec(select(func.count(User.id)).where(User.role == "customer")).one(),
                "revenue": session.exec(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status == "completed")).one()}

    application.include_router(api)
    if STATIC.exists():
        application.mount("/static", StaticFiles(directory=STATIC), name="static")

    @application.get("/", include_in_schema=False)
    def storefront():
        index = STATIC / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"message": "FlowerShop сервері дайын", "docs": "/docs"}

    return application


app = create_app()
