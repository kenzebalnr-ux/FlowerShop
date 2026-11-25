"""Қайталанып іске қосылғанда көшірме жазба қоспайтын бастапқы деректер."""
from datetime import date
import os
import secrets

from sqlmodel import Session, select

from .db import init_db, make_engine
from .models import Category, Order, OrderItem, Product, User
from .schemas import Register
from .security import hash_password

IMAGES = [
    "photo-1561181286-d3fee7d55364", "photo-1520763185298-1b434c919102",
    "photo-1525310072745-f49212b5ac6d", "photo-1457089328109-e5d9bd499191",
    "photo-1490750967868-88aa4486c946", "photo-1563241527-3004b7be0ffd",
]

PRODUCTS = [
    ("Нәзік сезім", "Ақ және алқызыл раушаннан жиналған әсем гүлшоғы. Жақын адамыңызға жылы сезім сыйлаңыз.", 18900, 21900, 1, 0, "Туған күн", "Көп таңдалған"),
    ("Көктем шуағы", "Жаңа жиналған қызғалдақтар. Көктемнің жарқын түстері мен жеңіл көңіл күйі.", 12900, None, 2, 1, "Алғыс айту", "Маусым таңдауы"),
    ("Махаббат хаты", "Қанық қызыл раушан гүлдері мен талғампаз қаптама. Ең маңызды сөздерге лайық сыйлық.", 24900, 27900, 1, 2, "Махаббат", "Танымал"),
    ("Ақ арман", "Ақ раушан мен нәзік жасыл жапырақтар үйлесімі. Классикалық әрі ерекше композиция.", 21900, None, 1, 3, "Үйлену тойы", ""),
    ("Күн сәулесі", "Күншуақты реңктердегі авторлық гүлшоғы. Күнделікті сәтті ерекше қуанышқа айналдырады.", 15900, None, 3, 4, "Туған күн", "Жаңа"),
    ("Гүлдер әуені", "Маусым гүлдерінің пастельді композициясы. Флорист ұқыппен жинаған ерекше сыйлық.", 28900, 32900, 3, 5, "Мерейтой", "Флорист таңдауы"),
    ("Қызғылт бұлт", "Нәзік қызғылт гүлдерден құралған көлемді гүлшоғы. Әр жапырағында ерекше жылылық бар.", 19900, None, 3, 0, "Махаббат", ""),
    ("Шексіз қуаныш", "Сәнді қораптағы үйлесімді гүлдер. Сыйлыққа дайын, күтімі жеңіл композиция.", 32900, 36900, 4, 1, "Мерейтой", "Премиум"),
    ("Көктем лебі", "Түрлі түсті қызғалдақтардың жарқын шоғы. Жақындарыңызға жақсы көңіл күй сыйлаңыз.", 14900, None, 2, 4, "Алғыс айту", ""),
    ("Сырлы бақ", "Табиғи пішіндегі авторлық композиция. Маусымдық гүлдер мен жасыл жапырақтар үйлесімі.", 26900, None, 3, 3, "Туған күн", "Авторлық"),
    ("Жүрек жылуы", "Ықшам қораптағы әсем раушандар. Шағын әрі есте қалатын сыйлық.", 23900, None, 4, 2, "Махаббат", ""),
    ("Ерекше сәт", "Салтанатты мерекеге арналған үлкен гүл композициясы. Талғампаз түстер, әдемі қаптама.", 39900, None, 4, 5, "Мерейтой", "Премиум"),
]


def seed_database(engine):
    with Session(engine) as session:
        if session.exec(select(Category)).first() is None:
            for name, slug in [("Раушандар", "roses"), ("Қызғалдақтар", "tulips"),
                               ("Авторлық гүлшоқтар", "bouquets"), ("Қораптағы гүлдер", "boxes")]:
                session.add(Category(name=name, slug=slug))
            session.flush()
            for name, desc, price, old, category, photo, occasion, badge in PRODUCTS:
                session.add(Product(name=name, description=desc, price=price, old_price=old,
                                    category_id=category, image_url=f"https://images.unsplash.com/{IMAGES[photo]}?auto=format&fit=crop&w=900&q=85",
                                    stock=30, occasion=occasion, badge=badge))
            # Lab 2: three clearly fictional customers with unknown random passwords.
            # Example orders belong only to these accounts and never appear for real signups.
            for index, name in enumerate(["Үлгі: Айдана", "Үлгі: Әли", "Үлгі: Мадина"], 1):
                user = User(name=name, email=f"sample{index}@example.invalid",
                            password_hash=hash_password(secrets.token_urlsafe(32)))
                session.add(user)
                session.flush()
                product = session.get(Product, index)
                order = Order(number=f"FS-DEMO-{index:03}", user_id=user.id,
                              recipient_name=name, phone="+77000000000", address="Оқу үлгісі",
                              delivery_method="pickup", delivery_date=date.today().isoformat(),
                              time_slot="Кез келген уақытта", subtotal=product.price,
                              discount=0, delivery_fee=0, total=product.price, status="completed")
                session.add(order)
                session.flush()
                session.add(OrderItem(order_id=order.id, product_id=product.id,
                                      product_name=product.name, image_url=product.image_url,
                                      quantity=1, unit_price=product.price))
            session.commit()
        admin_password = os.getenv("FLOWERSHOP_ADMIN_PASSWORD")
        if admin_password:
            email = os.getenv("FLOWERSHOP_ADMIN_EMAIL", "admin@flowershop.kz").lower()
            Register(name="Әкімші", email=email, password=admin_password)
            user = session.exec(select(User).where(User.email == email)).first()
            if user is None:
                session.add(User(name="Әкімші", email=email, password_hash=hash_password(admin_password), role="admin"))
                session.commit()
            elif user.role != "admin":
                raise RuntimeError("Әкімші поштасы клиентке тиесілі. Басқа FLOWERSHOP_ADMIN_EMAIL таңдаңыз.")


if __name__ == "__main__":
    engine = make_engine()
    init_db(engine)
    seed_database(engine)
    print("FlowerShop: бастапқы деректер дайын.")
