"""Зертханаға арналған Streamlit басқару интерфейсі."""
import os
import pandas as pd
import requests
import streamlit as st

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(page_title="FlowerShop · Басқару", page_icon="🌷", layout="wide")
st.markdown("""<style>.stApp{background:#faf8f6}h1,h2,h3{color:#264a3b}[data-testid=stSidebar]{background:#edf2ec}div.stButton>button[kind=primary]{background:#315a46;border-color:#315a46}.block-container{padding-top:2rem}</style>""", unsafe_allow_html=True)
st.session_state.setdefault("token", "")
st.session_state.setdefault("user", None)


def api(method, path, **kwargs):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    try:
        response = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=12, **kwargs)
    except requests.RequestException:
        st.error("Сервермен байланыс орнатылмады. Backend іске қосылғанын тексеріңіз.")
        return None
    if not response.ok:
        try:
            detail = response.json().get("detail", "Сұрау орындалмады")
            if isinstance(detail, list):
                detail = "; ".join(str(item.get("msg", "Қате мән")) for item in detail)
        except ValueError:
            detail = "Сервер сұрауды қабылдамады"
        st.error(f"{response.status_code}: {detail}")
        return None
    return response.json() if response.content else {"ok": True}


with st.sidebar:
    st.markdown("## 🌷 FlowerShop")
    st.caption("Гүлдер мен тапсырыстарды басқару")
    st.link_button("Дүкен витринасын ашу", os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8000"))
    st.divider()
    if st.session_state.user:
        st.write(st.session_state.user.get("name", "Пайдаланушы"))
        st.caption("Әкімші" if st.session_state.user.get("role") == "admin" else "Сатып алушы")
        if st.button("Шығу", use_container_width=True):
            api("POST", "/api/auth/logout")
            st.session_state.token = ""
            st.session_state.user = None
            st.rerun()
    else:
        st.markdown("### Жүйеге кіру")
        with st.form("login"):
            email = st.text_input("Электрондық пошта", placeholder="admin@flowershop.kz")
            password = st.text_input("Құпиясөз", type="password")
            submit = st.form_submit_button("Кіру", use_container_width=True, type="primary")
        if submit:
            result = api("POST", "/api/auth/login", json={"email": email, "password": password})
            if result:
                st.session_state.token = result["access_token"]
                st.session_state.user = result["user"]
                st.rerun()
        st.caption("Әкімші құпиясөзін серверді іске қосатын адам .env арқылы орнатады.")
    st.divider()
    st.caption("Зертхана интерфейсі · Streamlit + FastAPI")

st.title("Гүлдер әлемін басқарыңыз")
st.write("Каталог, қойма және тапсырыстар — бір жерде.")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))
categories = api("GET", "/api/categories")
if categories is None:
    st.stop()
category_names = {c["id"]: c["name"] for c in categories}
cols = st.columns([3, 2, 1, 1])
with cols[0]:
    search = st.text_input("Гүлді іздеу", placeholder="Мысалы, раушан")
with cols[1]:
    category = st.selectbox("Санат", [None] + list(category_names), format_func=lambda x: "Барлық санат" if x is None else category_names[x])
with cols[2]:
    minimum = st.number_input("Ең төмен баға, ₸", min_value=0, value=0, step=1000)
with cols[3]:
    maximum = st.number_input("Ең жоғары баға, ₸", min_value=0, value=10000000, step=1000)
params = {"search": search, "min_price": minimum, "max_price": maximum}
if category is not None:
    params["category_id"] = category
products = api("GET", "/api/products", params=params)
if products is None:
    st.stop()
metrics = st.columns(3)
metrics[0].metric("Табылған гүл шоқтары", len(products))
metrics[1].metric("Қоймадағы дана", sum(p["stock"] for p in products))
metrics[2].metric("Санаттар", len(categories))
if products:
    rows = [{"ID": p["id"], "Атауы": p["name"], "Санат": category_names.get(p["category_id"], "—"), "Бағасы, ₸": p["price"], "Қойма": p["stock"], "Белгі": p.get("badge", "")} for p in products]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Бұл шарттарға сәйкес гүл табылмады. Іздеу мен сүзгіні өзгертіңіз.")

if not st.session_state.user or st.session_state.user.get("role") != "admin":
    st.info("Каталогты қарауға болады. Тауарлар мен тапсырыстарды өзгерту үшін әкімші ретінде кіріңіз.")
    st.stop()

add_tab, edit_tab, orders_tab = st.tabs(["Гүл шоғын қосу", "Өзгерту және жою", "Тапсырыстар"])
with add_tab:
    with st.form("add_product", clear_on_submit=True):
        name = st.text_input("Гүл шоғының атауы")
        description = st.text_area("Сипаттамасы")
        a, b, c = st.columns(3)
        price = a.number_input("Баға, ₸", min_value=1, value=15000, max_value=10000000)
        stock = b.number_input("Қоймадағы саны", min_value=0, value=20, max_value=100000)
        cid = c.selectbox("Санаты", list(category_names), format_func=category_names.get)
        image_url = st.text_input("Суреттің HTTPS сілтемесі", value="https://images.unsplash.com/photo-1561181286-d3fee7d55364?w=800&q=85")
        occasion = st.text_input("Қандай мерекеге", value="Кез келген күн")
        badge = st.text_input("Карточка белгісі", placeholder="Жаңа")
        create = st.form_submit_button("Каталогқа қосу", type="primary")
    if create:
        result = api("POST", "/api/products", json={"name": name, "description": description, "price": price, "stock": stock, "category_id": cid, "image_url": image_url, "occasion": occasion, "badge": badge})
        if result:
            st.session_state.flash = "Гүл шоғы каталогқа қосылды."
            st.rerun()
with edit_tab:
    if products:
        by_id = {p["id"]: p for p in products}
        chosen_id = st.selectbox("Өзгертілетін тауар", list(by_id), format_func=lambda x: f"#{x} · {by_id[x]['name']}")
        chosen = by_id[chosen_id]
        with st.form(f"edit_{chosen_id}"):
            new_name = st.text_input("Атауы", chosen["name"])
            new_description = st.text_area("Сипаттамасы", chosen["description"])
            a, b = st.columns(2)
            new_price = a.number_input("Жаңа баға, ₸", min_value=1, max_value=10000000, value=chosen["price"])
            new_stock = b.number_input("Жаңа қойма саны", min_value=0, max_value=100000, value=chosen["stock"])
            if st.form_submit_button("Өзгерістерді сақтау", type="primary"):
                result = api("PATCH", f"/api/products/{chosen_id}", json={"name": new_name, "description": new_description, "price": new_price, "stock": new_stock})
                if result:
                    st.session_state.flash = "Тауар жаңартылды."
                    st.rerun()
        confirmed = st.checkbox("Осы тауарды каталогтан жоюды растаймын", key=f"delete_confirm_{chosen_id}")
        if st.button("Тауарды жою", disabled=not confirmed):
            result = api("DELETE", f"/api/products/{chosen_id}")
            if result is not None:
                st.session_state.flash = "Тауар каталогтан жойылды."
                st.rerun()
    else:
        st.info("Өңдеу үшін каталогта тауар болуы керек.")
with orders_tab:
    orders = api("GET", "/api/admin/orders")
    labels = {"new": "Жаңа", "confirmed": "Расталды", "preparing": "Дайындалуда", "delivering": "Жеткізілуде", "completed": "Аяқталды", "cancelled": "Бас тартылды"}
    if orders:
        st.dataframe(pd.DataFrame([{"Нөмір": o["number"], "Алушы": o["recipient_name"], "Телефон": o["phone"], "Сома, ₸": o["total"], "Күйі": labels.get(o["status"], o["status"]), "Күні": o["delivery_date"]} for o in orders]), use_container_width=True, hide_index=True)
        lookup = {o["id"]: o for o in orders}
        oid = st.selectbox("Тапсырысты таңдау", list(lookup), format_func=lambda x: lookup[x]["number"])
        transitions = {"new": ["confirmed", "cancelled"], "confirmed": ["preparing", "cancelled"], "preparing": ["delivering", "cancelled"], "delivering": ["completed"], "completed": [], "cancelled": []}
        current = lookup[oid]["status"]
        status = st.selectbox("Жаңа күйі", [current] + transitions.get(current, []), format_func=labels.get)
        if st.button("Тапсырыс күйін сақтау", type="primary"):
            if api("PATCH", f"/api/admin/orders/{oid}", json={"status": status}):
                st.session_state.flash = "Тапсырыс күйі жаңартылды."
                st.rerun()
    elif orders is not None:
        st.info("Әзірше тапсырыс жоқ.")
