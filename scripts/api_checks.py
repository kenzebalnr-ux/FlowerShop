"""№8 зертхана: оқшауланған HTTP серверіне requests арқылы API тексерістері.

Іске қосу: python scripts/api_checks.py
Нақты дүкеннің деректер қорына қосылмайды; уақытша SQLite автоматты жойылады.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

import requests
from sqlmodel import Session, select
import uvicorn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
SECRET_KEYS = {"access_token", "password", "password_hash", "token", "token_hash", "authorization"}


def sanitized(value):
    """Токендер мен құпиясөздер ешқашан есепке түспейді."""
    if isinstance(value, dict):
        return {key: "[ЖАСЫРЫЛДЫ]" if key.lower() in SECRET_KEYS else sanitized(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized(item) for item in value[:2]]
    return value


def main():
    parser = argparse.ArgumentParser(description="FlowerShop оқшауланған HTTP API тексерісі")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/results/api-checks.json")
    args = parser.parse_args()
    records = []
    server = None
    thread = None
    application = None
    module = None
    failure = None
    previous_db = os.environ.get("DATABASE_URL")
    previous_admin = os.environ.pop("FLOWERSHOP_ADMIN_PASSWORD", None)
    client = requests.Session()
    # A local QA probe must not use a machine's external HTTP proxy.
    client.trust_env = False

    try:
        with tempfile.TemporaryDirectory(prefix="flowershop-api-qa-") as temporary:
            database_url = "sqlite:///" + (Path(temporary) / "qa.db").as_posix()
            os.environ["DATABASE_URL"] = database_url
            try:
                module = importlib.import_module("backend.main")
                application = module.create_app(database_url)
                config = uvicorn.Config(application, host="127.0.0.1", port=args.port,
                                        log_level="warning", access_log=False,
                                        timeout_graceful_shutdown=5)
                server = uvicorn.Server(config)
                thread = threading.Thread(target=server.run, daemon=True, name="flowershop-api-qa")
                thread.start()
                base = f"http://127.0.0.1:{args.port}"
                deadline = time.monotonic() + 15
                while not server.started:
                    if not thread.is_alive() or time.monotonic() > deadline:
                        raise RuntimeError("Оқшауланған API сервері іске қосылмады.")
                    time.sleep(0.05)

                def check(method, path, expected, *, label, headers=None, **kwargs):
                    response = client.request(method, base + path, headers=headers, timeout=8, **kwargs)
                    try:
                        body = response.json() if response.content else None
                    except ValueError:
                        body = "JSON емес жауап"
                    record = {"label": label, "method": method, "path": path,
                              "expected_status": expected, "actual_status": response.status_code,
                              "passed": response.status_code == expected,
                              "body_sample": sanitized(body)}
                    records.append(record)
                    if not record["passed"]:
                        raise RuntimeError(f"{method} {path}: {response.status_code}, күтілгені {expected}")
                    return body

                accounts = []
                for role in ("admin", "customer"):
                    email = f"qa-{role}-{secrets.token_hex(5)}@example.invalid"
                    password = secrets.token_urlsafe(20) + "A1"
                    response = client.post(base + "/api/auth/register", timeout=8,
                                           json={"name": "API сынақ пайдаланушысы", "email": email,
                                                 "password": password})
                    if response.status_code != 201:
                        raise RuntimeError("Уақытша сынақ аккаунты құрылмады.")
                    accounts.append((email, {"Authorization": "Bearer " + response.json()["access_token"]}))

                # Privilege assignment is confined to the temporary QA database.
                from backend.models import User
                with Session(application.state.engine) as db:
                    admin = db.exec(select(User).where(User.email == accounts[0][0])).one()
                    admin.role = "admin"
                    db.add(admin)
                    db.commit()
                admin_headers, customer_headers = accounts[0][1], accounts[1][1]
                check("GET", "/api/products", 200, label="Каталогты алу")
                product = {"name": "API сынақ гүлі", "description": "Оқшауланған HTTP тексерісінің тауары",
                           "price": 12000, "category_id": 1, "stock": 5}
                created = check("POST", "/api/products", 201, label="Жаңа тауар қосу",
                                headers=admin_headers, json=product)
                path = f"/api/products/{created['id']}"
                check("PUT", path, 200, label="Тауарды толық жаңарту", headers=admin_headers,
                      json={**product, "price": 15000})
                check("DELETE", path, 204, label="Тауарды физикалық жою", headers=admin_headers)
                check("POST", "/api/products", 400, label="Қате JSON қабылданбайды", headers={
                    **admin_headers, "Content-Type": "application/json"}, data='{"name":')
                check("GET", path, 404, label="Жойылған тауар табылмайды")
                check("GET", "/api/orders", 401, label="Авторизациясыз қорғалған ресурс")
                check("POST", "/api/products", 403, label="Клиент әкімші әрекетін жасай алмайды",
                      headers=customer_headers, json=product)
            finally:
                client.close()
                if server is not None:
                    server.should_exit = True
                if thread is not None:
                    thread.join(timeout=10)
                    if thread.is_alive():
                        server.force_exit = True
                        thread.join(timeout=5)
                if application is not None:
                    application.state.engine.dispose()
                if module is not None:
                    module.app.state.engine.dispose()
    except Exception as error:
        # Arbitrary exception text can contain SQL parameters; keep the report secret-free.
        failure = f"Тексеріс аяқталмады ({type(error).__name__}). Соңғы тексеріс нәтижесін қараңыз."
    finally:
        if previous_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db
        if previous_admin is not None:
            os.environ["FLOWERSHOP_ADMIN_PASSWORD"] = previous_admin

    report = {"title": "FlowerShop: requests арқылы HTTP интеграциялық тексеріс",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "environment": "Уақытша SQLite және тек 127.0.0.1 мекенжайындағы Uvicorn",
              "passed": failure is None and len(records) == 8,
              "checks": records, "error": failure}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"HTTP API: {sum(item['passed'] for item in records)}/{len(records)} тексеріс өтті.")
    if failure:
        print(failure)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
