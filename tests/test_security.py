import pytest
from sqlmodel import Session, select
from backend.models import User
from conftest import register
from test_integration import checkout

pytestmark=pytest.mark.security


@pytest.mark.parametrize('password',['','123','password','12345678'])
def test_weak_password_rejected(client,password):
    response=client.post('/api/auth/register',json={'name':'Сынақ','email':'weak@example.com','password':password})
    assert response.status_code==400
    # The field name "password" is allowed metadata; never echo its submitted value in the message.
    assert password not in response.json()['detail'] or len(password)<4


def test_wrong_login(client,customer):
    response=client.post('/api/auth/login',json={'email':'test@example.com','password':'WrongPass!2026'})
    assert response.status_code==401
    assert 'access_token' not in response.text


def test_protected_resources_need_login(client):
    for route in ['/api/auth/me','/api/orders','/api/admin/orders']:
        assert client.get(route).status_code==401


def test_customer_cannot_admin(client,customer):
    assert client.get('/api/admin/orders',headers=customer).status_code==403
    assert client.delete('/api/products/1',headers=customer).status_code==403


def test_malformed_json_and_no_secret_leaks(client):
    response=client.post('/api/auth/register',content='{broken',headers={'Content-Type':'application/json'})
    assert response.status_code==400
    for secret in ['Traceback','password_hash','sqlite','SELECT','{broken']:
        assert secret not in response.text


def test_password_hash_and_public_user(client,customer):
    response=client.get('/api/auth/me',headers=customer)
    assert response.status_code==200 and 'password' not in response.text and 'hash' not in response.text
    with Session(client.app.state.engine) as session:
        user=session.exec(select(User).where(User.email=='test@example.com')).one()
        assert user.password_hash!='FlowerTest!2026'
        assert 'FlowerTest!2026' not in user.password_hash


def test_order_ownership(client,customer):
    order=client.post('/api/orders',json=checkout(),headers=customer).json()
    second=register(client,'second@example.com')
    headers={'Authorization':f"Bearer {second['access_token']}"}
    assert client.get(f"/api/orders/{order['id']}",headers=headers).status_code==404
    assert not client.get('/api/orders',headers=headers).json()


def test_logout_revokes_token(client,customer):
    assert client.post('/api/auth/logout',headers=customer).status_code in (200,204)
    assert client.get('/api/auth/me',headers=customer).status_code==401


@pytest.mark.parametrize('quantity',[0,-1,1.5,1001])
def test_invalid_order_quantities(client,customer,quantity):
    assert client.post('/api/orders',json=checkout(quantity=quantity),headers=customer).status_code==400


def test_client_cannot_set_price_or_role(client,customer):
    payload=checkout(); payload['total']=1
    response=client.post('/api/orders',json=payload,headers=customer)
    assert response.status_code==400
    response=client.post('/api/auth/register',json={'name':'Сынақ','email':'role@example.com','password':'FlowerTest!2026','role':'admin'})
    assert response.status_code==400


def test_sql_injection_search_is_data(client):
    response=client.get('/api/products',params={'search':"' OR 1=1 --"})
    assert response.status_code==200 and response.json()==[]
    assert len(client.get('/api/products').json())>=10


def test_password_not_logged(client,caplog):
    register(client)
    assert 'FlowerTest!2026' not in caplog.text

