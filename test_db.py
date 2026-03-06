import sys
sys.path.append('.')
from app import db, Order, app
import json

with app.app_context():
    # Test insert
    order = Order(table_no='2', items=json.dumps(['Test x1']), total=50.0, status='PLACED')
    db.session.add(order)
    db.session.commit()
    print('Inserted order id:', order.id)

    # Test query
    orders = Order.query.all()
    print('Total orders:', len(orders))
    for o in orders:
        print(f'ID: {o.id}, Table: {o.table_no}, Items: {o.items}, Total: {o.total}, Status: {o.status}')