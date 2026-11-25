from datetime import date, timedelta
import pytest
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from backend.models import Category, Product, Order
from conftest import register


def checkout(product_id=1, quantity=1, **changes):
    payload = dict(items=[dict(product_id=product_id, quantity=quantity)],
                   recipient_name='Айгүл Сынақ', phone='+77011234567',
                   address='Алматы, Абай көшесі 10', delivery_method='courier',
                   delivery_date=(date.today()+timedelta(days=1)).isoformat(),
                   time_slot='10:00–13:00', card_message='Ізгі тілекпен', promo_code='')
    payload.update(changes)
    return payload


@pytest.mark.integration
def test_catalog_and_detail(client):
    categories = client.get('/api/categories')
    assert categories.status_code == 200 and len(categories.json()) >= 3
    products = client.get('/api/products')
    assert products.status_code == 200 and len(products.json()) >= 10
    item = products.json()[0]
    assert client.get(f"/api/products/{item['id']}").json()['name'] == item['name']


@pytest.mark.integration
def test_search_filter_and_sort(client):
    products = client.get('/api/products', params={'min_price':10000,'max_price':20000,'sort':'price_asc'}).json()
    assert products and all(10000 <= p['price'] <= 20000 for p in products)
    assert [p['price'] for p in products] == sorted(p['price'] for p in products)
    name = products[0]['name']
    assert any(p['name']==name for p in client.get('/api/products', params={'search':name}).json())
    assert client.get('/api/products', params={'search':'zzzz-no-result'}).json()==[]


def test_not_found(client):
    assert client.get('/api/products/999999').status_code == 404


@pytest.mark.integration
def test_product_crud(client, admin):
    payload = {'name':'Сынақ шоғы','description':'Зертханаға арналған гүл шоғы','price':12300,'category_id':1,'stock':5}
    created = client.post('/api/products', json=payload, headers=admin)
    assert created.status_code == 201, created.text
    pid = created.json()['id']
    patched = client.patch(f'/api/products/{pid}', json={'price':13000}, headers=admin)
    assert patched.status_code == 200 and patched.json()['name']==payload['name']
    payload['name']='Жаңартылған гүл'; payload['price']=14000
    updated = client.put(f'/api/products/{pid}', json=payload, headers=admin)
    assert updated.status_code == 200 and updated.json()['price']==14000
    assert client.delete(f'/api/products/{pid}', headers=admin).status_code in (200,204)
    assert client.get(f'/api/products/{pid}').status_code==404


@pytest.mark.integration
def test_order_persists_and_stock_decreases(client, customer):
    before = client.get('/api/products/1').json()
    response = client.post('/api/orders', json=checkout(), headers=customer)
    assert response.status_code == 201, response.text
    order=response.json()
    assert order['subtotal']==before['price']
    assert order['total']==order['subtotal']-order['discount']+order['delivery_fee']
    assert client.get('/api/products/1').json()['stock']==before['stock']-1
    assert client.get(f"/api/orders/{order['id']}",headers=customer).status_code==200
    assert any(o['id']==order['id'] for o in client.get('/api/orders',headers=customer).json())


def test_promo_and_pickup(client, customer):
    price=client.get('/api/products/1').json()['price']
    response=client.post('/api/orders',json=checkout(delivery_method='pickup',promo_code='GUL10'),headers=customer)
    assert response.status_code==201,response.text
    order=response.json()
    assert order['discount']==price//10 and order['delivery_fee']==0
    assert order['total']==price-price//10


def test_duplicate_lines_do_not_oversell(client, customer):
    product=client.get('/api/products/1').json()
    response=client.post('/api/orders',json=checkout(items=[{'product_id':1,'quantity':product['stock']},{'product_id':1,'quantity':product['stock']}]),headers=customer)
    assert response.status_code in (400,409)
    assert client.get('/api/products/1').json()['stock']==product['stock']


@pytest.mark.integration
def test_failed_order_rolls_back_all_items(client, customer):
    before=client.get('/api/products/1').json()['stock']
    with Session(client.app.state.engine) as session:
        count=len(session.exec(select(Order)).all())
    response=client.post('/api/orders',json=checkout(items=[{'product_id':1,'quantity':1},{'product_id':999999,'quantity':1}]),headers=customer)
    assert response.status_code in (400,404,409)
    assert client.get('/api/products/1').json()['stock']==before
    with Session(client.app.state.engine) as session:
        assert len(session.exec(select(Order)).all())==count


@pytest.mark.integration
def test_database_crud_and_rollback(client):
    with Session(client.app.state.engine) as session:
        category=Category(name='Дерекқор сынағы', slug='db-test')
        session.add(category); session.commit(); session.refresh(category)
        identifier=category.id
        assert session.get(Category,identifier).name=='Дерекқор сынағы'
        category.name='Өзгертілді'; session.add(category); session.commit()
        assert session.get(Category,identifier).name=='Өзгертілді'
        session.delete(category); session.commit()
        assert session.get(Category,identifier) is None
        before=len(session.exec(select(Category)).all())
        session.add(Category(name='Кері қайтарылуы керек', slug='rollback'))
        session.add(Category(name=None, slug='invalid'))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert len(session.exec(select(Category)).all())==before


