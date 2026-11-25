import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from backend.main import create_app
from backend.models import User


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


def register(client, email="test@example.com"):
    response = client.post('/api/auth/register', json={
        'name': 'Сынақ пайдаланушысы', 'email': email, 'password': 'FlowerTest!2026'
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def customer(client):
    data = register(client)
    return {'Authorization': f"Bearer {data['access_token']}"}


@pytest.fixture
def admin(client):
    data = register(client, 'admin-test@example.com')
    with Session(client.app.state.engine) as session:
        user = session.exec(select(User).where(User.email == 'admin-test@example.com')).one()
        user.role = 'admin'
        session.add(user)
        session.commit()
    return {'Authorization': f"Bearer {data['access_token']}"}

