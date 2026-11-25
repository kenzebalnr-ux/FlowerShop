"""Тек жергілікті немесе өзіңізге тиесілі сынақ ортасына арналған."""
from locust import HttpUser, task, between


class FlowerShopVisitor(HttpUser):
    wait_time=between(0.4,1.2)

    @task(4)
    def catalog(self):
        self.client.get('/api/products',name='Каталог')

    @task(2)
    def detail(self):
        self.client.get('/api/products/1',name='Гүл мәліметі')

    @task(2)
    def search(self):
        self.client.get('/api/products',params={'min_price':10000,'max_price':25000},name='Баға сүзгісі')

    @task(1)
    def categories(self):
        self.client.get('/api/categories',name='Санаттар')

