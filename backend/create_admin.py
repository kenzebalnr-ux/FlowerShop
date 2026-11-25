"""Іске қосу: python -m backend.create_admin. Құпиясөз экранға шықпайды."""
from getpass import getpass
from sqlmodel import Session, select

from .db import init_db, make_engine
from .models import User
from .schemas import Register
from .security import hash_password


def main():
    email = input("Әкімшінің электрондық поштасы: ").strip().lower()
    password = getpass("Құпиясөз (8+ таңба, әріп және сан): ")
    confirmation = getpass("Құпиясөзді қайталаңыз: ")
    if password != confirmation:
        raise SystemExit("Құпиясөздер сәйкес емес.")
    data = Register(name="Әкімші", email=email, password=password)
    engine = make_engine()
    init_db(engine)
    with Session(engine) as session:
        if session.exec(select(User).where(User.email == data.email)).first():
            raise SystemExit("Бұл пошта тіркелген. Басқа поштаны қолданыңыз.")
        session.add(User(name=data.name, email=data.email, password_hash=hash_password(data.password), role="admin"))
        session.commit()
    print("Әкімші құрылды. Дүкенде немесе Streamlit панелінде кіріңіз.")


if __name__ == "__main__":
    main()
