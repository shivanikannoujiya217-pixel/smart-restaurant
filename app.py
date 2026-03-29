import sqlite3
from flask import Flask, request, jsonify, render_template, session, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json, os
from reportlab.pdfgen import canvas
from flask_socketio import SocketIO
import razorpay
import urllib.parse
from flask_cors import CORS




app = Flask(__name__)
CORS(app, origins=["https://voluble-hamster-8f55d1.netlify.app/user-dashboard.html"])
app.secret_key = "secret"

# Socket.IO for real-time updates
socketio = SocketIO(app, cors_allowed_origins='*')



# Razorpay
razorpay_client = razorpay.Client(
    auth=("rzp_test_XXXXXXXX", "rzp_test_secret")
)

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def ensure_db_columns():
    # Ensure orders table has a created_at column for reporting
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    # If the table doesn't exist, cols will be empty — caller should ensure tables are created first
    try:
        if 'created_at' not in cols:
            cur.execute("ALTER TABLE orders ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
        if 'payment_token' not in cols:
            cur.execute("ALTER TABLE orders ADD COLUMN payment_token TEXT")
        if 'razorpay_order_id' not in cols:
            cur.execute("ALTER TABLE orders ADD COLUMN razorpay_order_id TEXT")
        if 'paid_amount' not in cols:
            cur.execute("ALTER TABLE orders ADD COLUMN paid_amount FLOAT DEFAULT 0")
        conn.commit()
    except Exception:
        # If alter fails (e.g., table missing), ignore — caller should have created tables
        pass
    conn.close()

# ======================= MODELS =======================

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    price = db.Column(db.Float)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    table_no = db.Column(db.String(10))
    items = db.Column(db.Text)
    total = db.Column(db.Float)
    status = db.Column(db.String(20), default="paid")
    


# ======================= USER SIDE =======================

@app.route("/")
def home():
    return "API Running"
@app.route("/user")
def user():
    return render_template("user-dashboard.html")

@app.route('/')
@app.route('/user-dashboard/<tableno>')
def user_dashboard(tableno='1'):
    return render_template('user-dashboard.html', tableno=tableno)
    
@app.route('/admin/dashboard')
def admin_dashboard():

    conn = sqlite3.connect("restaurant.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    cur.execute("SELECT SUM(total) FROM orders WHERE status='PAID'")
    total_sales = cur.fetchone()[0] or 0

    conn.close()

    return render_template(
        "dashboard.html",
        orders=orders,
        total_sales=total_sales
    )
@app.route('/api/menu')
def get_menu():
    items = Menu.query.all()
    return jsonify([
        {'id': i.id, 'name': i.name, 'category': i.category, 'price': i.price}
        for i in items
    ])

@app.route('/admin/menu', methods=['POST'])
def save_menu():
    # insert / update menu_items
    return jsonify({"status": "ok"})

@app.route('/place-order', methods=['POST'])
def place_order():
    data = request.get_json()

    table_no = data['table_no']
    items = json.dumps(data['items'])
    total = data['total']   step4 walcode add karo

    con = sqlite3.connect("restaurant.db")
    cur = con.cursor()

    # create order with initial status PLACED (will be updated when admin accepts / prepares)
    cur.execute("""
        INSERT INTO orders (table_no, items, total, status)
        VALUES (?, ?, ?, ?)
    """, (table_no, items, total, "Paid"))

    order_id = cur.lastrowid
    con.commit()

    # Emit real-time event so user's phone and admin dashboards can update
    try:
        socketio.emit('order_update', {
            'order_id': order_id,
            'table_no': table_no,
            'status': 'Paid',
            'total': total
        }, broadcast=True)
    except Exception:
        pass

    con.close()

    return jsonify({"success": True, "order_id": order_id})




# clear orders
@app.route('/api/clear-orders', methods=['POST'])
def clear_orders():
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM orders")

    conn.commit()
    conn.close()

    return {"status":"cleared"}


@app.route('/api/orders')
def api_orders():

    conn = sqlite3.connect("restaurant.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cur.fetchall()

    orders = []

    for r in rows:
        try:
            items = json.loads(r["items"]) if r["items"] else []
        except:
            items = []

        orders.append({
            "id": r["id"],
            "table_no": r["table_no"],
            "items": items,
            "total": r["total"],
            "status": r["status"]
        })

    conn.close()

    return jsonify(orders)


# ======================= ADMIN AUTH =======================


@app.route('/admin/login')
def admin_login_page():
    return render_template('adminlogin.html')


@app.route('/adminlogin', methods=['POST'])
def admin_login():
    data = request.get_json(force=True)
    if data['username'] == 'admin' and data['password'] == 'admin123':
        session['admin'] = True
        return jsonify(success=True, redirect='/admin')
    return jsonify(success=False)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')
from flask import render_template


import json
import sqlite3
from datetime import datetime
import sqlite3, json
from flask import render_template

@app.route('/bill/<int:order_id>')
def show_bill(order_id):

    import sqlite3, json
    from datetime import datetime

    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()

    cur.execute("SELECT id, table_no, items, created_at FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Order not found"

    order_id, table_no, items_json, created_at = row

    # parse items (stored as list of dicts)
    try:
        items = json.loads(items_json) if items_json else []
    except Exception:
        items = []

    # compute totals from items reliably
    subtotal_val = 0.0
    for it in items:
        try:
            price = float(it.get('price', 0)) if isinstance(it, dict) else 0
            qty = int(it.get('qty', 0)) if isinstance(it, dict) else 0
        except Exception:
            price = 0
            qty = 0
        subtotal_val += price * qty

    gst = round(subtotal_val * 0.05, 2)
    discount = 20
    total_val = round(subtotal_val + gst - discount, 2)

    # parse created_at safely (some rows may be NULL)
    try:
        if created_at:
            # try common formats
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = datetime.fromisoformat(created_at)
        else:
            dt = datetime.now()
    except Exception:
        dt = datetime.now()

    date = dt.strftime("%d %b %Y")
    time = dt.strftime("%I:%M %p")

    # include a small recent orders list for quick navigation in template
    conn2 = sqlite3.connect("restaurant.db")
    cur2 = conn2.cursor()
    try:
        cur2.execute("SELECT id FROM orders ORDER BY id DESC LIMIT 5")
        recent_orders = cur2.fetchall()
    finally:
        conn2.close()

    return render_template(
        "bill.html",
        order_id=order_id,
        table_no=table_no,
        items=items,
        subtotal=round(subtotal_val,2),
        gst=gst,
        discount=discount,
        total=total_val,
        date=date,
        time=time,
        orders=recent_orders
    )

from reportlab.pdfgen import canvas
from io import BytesIO
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from io import BytesIO
from flask import send_file
import json, sqlite3

@app.route('/bill/<int:order_id>/pdf')
def bill_pdf(order_id):
    con = sqlite3.connect("restaurant.db")
    cur = con.cursor()
    cur.execute(
        "SELECT id, table_no, items, total, status, created_at FROM orders WHERE id=?",
        (order_id,)
    )
    row = cur.fetchone()

    if not row:
        con.close()
        return "Order not found", 404

    # unpack row
    _, table_no, items_json, total_db, status, created_at = row

    try:
        items = json.loads(items_json) if items_json else []
    except Exception:
        items = []

    # compute display context (same as /bill route) so HTML looks identical
    subtotal_val = 0.0
    for it in items:
        try:
            price = float(it.get('price', 0)) if isinstance(it, dict) else 0
            qty = int(it.get('qty', 0)) if isinstance(it, dict) else 0
        except Exception:
            price = 0
            qty = 0
        subtotal_val += price * qty

    gst = round(subtotal_val * 0.05, 2)
    discount = 20
    total_val = round(subtotal_val + gst - discount, 2)

    try:
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = datetime.fromisoformat(created_at)
        else:
            dt = datetime.now()
    except Exception:
        dt = datetime.now()

    date = dt.strftime("%d %b %Y")
    time = dt.strftime("%I:%M %p")

    # render HTML from template with same variables
    html = render_template(
        "bill.html",
        order_id=order_id,
        table_no=table_no,
        items=items,
        subtotal=round(subtotal_val,2),
        gst=gst,
        discount=discount,
        total=total_val,
        date=date,
        time=time,
        orders=[(order_id,)]
    )

    # try pdfkit (wkhtmltopdf) to preserve HTML/CSS/images
    try:
        options = {
            'enable-local-file-access': None,
            'quiet': ''
        }
        pdf_bytes = pdfkit.from_string(html, False, options=options, css=None, configuration=None, toc=None)
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        con.close()
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"bill_{order_id}.pdf",
            mimetype="application/pdf"
        )
    except Exception:
        # fallback to ReportLab if pdfkit/wkhtmltopdf not available
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("<b>RESTAURANT BILL</b><br/><br/>", styles["Title"]))
        story.append(Paragraph(f"Order ID: {order_id}", styles["Normal"]))
        story.append(Paragraph(f"Table No: {table_no}<br/><br/>", styles["Normal"]))
        for i in items:
            if isinstance(i, dict):
                name = i.get('name', 'Item')
                qty = int(i.get('qty', 0))
                price = float(i.get('price', 0))
            else:
                name = str(i)
                qty = 0
                price = 0
            line = f"{name} x{qty} = Rs {qty * price:.2f}"
            story.append(Paragraph(line, styles["Normal"]))
        story.append(Paragraph(f"<br/><b>Total: Rs {total_val:.2f}</b>", styles["Normal"]))
        story.append(Paragraph(f"Status: {status}", styles["Normal"]))
        doc.build(story)
        buffer.seek(0)
        con.close()
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"bill_{order_id}.pdf",
            mimetype="application/pdf"
        )

def create_order(table_no, items, total):
    con = sqlite3.connect("restaurant.db")
    cur = con.cursor()

    items_json = json.dumps([{'name': n, 'qty': q, 'price': 0} for n, q in items])

    try:
        cur.execute(
            "INSERT INTO orders (table_no, items, total, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (table_no, items_json, total, "PAID", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    except Exception:
        cur.execute(
            "INSERT INTO orders (table_no, items, total, status) VALUES (?, ?, ?, ?)",
            (table_no, items_json, total, "PAID")
        )

    order_id = cur.lastrowid
    con.commit()
    con.close()
    return order_id


@app.route('/admin/order-status', methods=['POST'])
def order_status():
    # Accept either JSON or form-encoded data
    data = request.get_json(silent=True) or request.form
    order_id = data.get('order_id')
    status = data.get('status')

    if not order_id or not status:
        return jsonify({'success': False, 'error': 'order_id and status required'}), 400

    try:
        conn = sqlite3.connect("restaurant.db")
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        conn.commit()

        # Broadcast status change so user's phone updates in real time
        try:
            socketio.emit('order_update', {
                'order_id': int(order_id),
                'status': status
            }, broadcast=True)
        except Exception:
            pass

    finally:
        try:
            conn.close()
        except Exception:
            pass

    # If request came from admin form, redirect back to dashboard
    if request.form:
        return redirect(url_for('admin_dashboard'))
    return jsonify({'success': True})



@app.route('/payment-success/<int:order_id>')
def payment_success(order_id):

    order = {
        "id": order_id,
        "phone": "91XXXXXXXXXX",
        "customer_name": "Test User"
    }

    return render_template("payment_success.html", order=order)



# ======================= ADMIN DASHBOARD =======================

@app.route('/admin')
def admin_home():
    if not session.get('admin'):
        return redirect('/admin/login')
    return render_template('admin.html')


@app.route('/adminorders')
def admin_orders():
    orders = Order.query.all()
    return jsonify([
        {
            'id': o.id,
            'table': o.table_no,
            'items': json.loads(o.items),
            'total': o.total,
            'status': o.status
        } for o in orders
    ])
      
import os
print("DB PATH:", os.path.abspath("restaurant.db"))

import sqlite3
from flask import redirect, url_for

# ✅ ORDER RECEIVED

# ======================= PAYMENT =======================


@app.route('/admin/payment/<int:order_id>')
def admin_payment(order_id):
    return render_template('payment.html', order_id=order_id)
#
import uuid

# ---------------- QR GENERATE ----------------

@app.route('/generate-payment/<int:order_id>')
def generate_payment(order_id):

    token = str(uuid.uuid4())

    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()

    # Attach token and mark the order as PENDING so only this QR can be used
    cur.execute(
        "UPDATE orders SET payment_token=?, status='PENDING' WHERE id=?",
        (token, order_id)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "payment_url": f"/pay/{token}"
    })


# Backwards-compatible admin URL: some pages/linkers use /admin/generate-payment/
@app.route('/admin/generate-payment/<int:order_id>')
def admin_generate_payment(order_id):
    # reuse the same logic as generate_payment
    return generate_payment(order_id)

  
@app.route('/admin/bill/<int:table_no>')
def generate_bill(table_no):
    # find the most recent order for this table
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()
    cur.execute("SELECT id, table_no, items, total, status, created_at FROM orders WHERE table_no=? ORDER BY id DESC LIMIT 1", (table_no,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Order not found", 404

    order_id, table_no, items_json, total, status, created_at = row
    try:
        items = json.loads(items_json) if items_json else []
    except Exception:
        items = []

    # reuse show_bill rendering by redirecting to that route's template with same data
    # compute totals similar to show_bill
    subtotal_val = 0.0
    for it in items:
        if isinstance(it, dict):
            price = float(it.get('price', 0))
            qty = int(it.get('qty', 0))
        else:
            price = 0
            qty = 0
        subtotal_val += price * qty
    gst = round(subtotal_val * 0.05, 2)
    discount = 20
    total_val = round(subtotal_val + gst - discount, 2)

    # format created_at
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S") if created_at else datetime.now()
    except Exception:
        dt = datetime.now()

    date = dt.strftime("%d %b %Y")
    time = dt.strftime("%I:%M %p")

    return render_template("bill.html",
                           order_id=order_id,
                           table_no=table_no,
                           items=items,
                           subtotal=round(subtotal_val,2),
                           gst=gst,
                           discount=discount,
                           total=total_val,
                           date=date,
                           time=time,
                           orders=[(order_id,)])




@app.route("/print-bill/<int:order_id>")
def print_bill(order_id):
    order = Order.query.get_or_404(order_id)
    return send_file(order.bill_pdf, as_attachment=False)

from flask import send_file
import io
import smtplib

from flask import send_file
import sqlite3
import json
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

@app.route('/admin/download-bill/<int:order_id>')
def download_bill(order_id):
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT table_no, items, total, status FROM orders WHERE id = ?",
        (order_id,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return "Order not found"

    table_no, items_raw, total_db, status = row

    try:
        parsed = json.loads(items_raw) if items_raw else []
    except Exception:
        parsed = []

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    # ===== HEADER =====
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width / 2, height - 60, "SMART RESTAURANT")

    pdf.setFont("Helvetica", 12)
    pdf.setFont("Courier", 12)
    y -= 30

    now = datetime.now()
    pdf.drawString(60, y, f"Date: {now.strftime('%d %b %Y')}")
    y -= 20
    pdf.drawString(60, y, f"Time: {now.strftime('%I:%M %p')}")
    y -= 20
    pdf.drawString(60, y, f"Order ID: {order_id}")
    y -= 20
    pdf.drawString(60, y, f"Table: {table_no}")

    y -= 25
    pdf.drawString(60, y, "-" * 70)

    # ===== TABLE HEADER =====
    y -= 25
    pdf.drawString(60, y, "Item")
    pdf.drawString(350, y, "Qty")
    pdf.drawString(400, y, "Rate")
    pdf.drawString(470, y, "Total")

    y -= 15
    pdf.drawString(60, y, "-" * 70)

    # ===== ITEMS =====
    y -= 25
    subtotal = 0

    # parsed may be a list of dicts or a dict name->qty
    if isinstance(parsed, dict):
        items_iter = parsed.items()
    else:
        # convert list of dicts into (name, qty) pairs
        items_iter = []
        for it in parsed:
            if isinstance(it, dict):
                items_iter.append((it.get('name', 'Item'), int(it.get('qty', 0))))
            else:
                items_iter.append((str(it), 0))

    for name, qty in items_iter:
        # price fetch from menu table only if not provided in parsed data
        price = None
        try:
            # try to find price in menu
            cur.execute("SELECT price FROM menu WHERE name = ?", (name,))
            price_row = cur.fetchone()
            price = price_row[0] if price_row else 0
        except Exception:
            price = 0

        item_total = price * qty
        subtotal += item_total

        pdf.drawString(60, y, str(name))
        pdf.drawString(360, y, str(qty))
        pdf.drawString(410, y, f"{price:.2f}")
        pdf.drawString(480, y, f"{item_total:.2f}")
        y -= 25

    pdf.drawString(60, y, "-" * 70)

    # ===== TOTALS RIGHT SIDE =====
    gst = subtotal * 0.05
    discount = 20
    grand_total = subtotal + gst - discount

    y -= 40

    pdf.drawRightString(width - 60, y, f"Subtotal: Rs {round(subtotal,2):.2f}")
    y -= 20
    pdf.drawRightString(width - 60, y, f"GST (5%): Rs {round(gst,2):.2f}")
    y -= 20
    pdf.drawRightString(width - 60, y, f"Discount: Rs {discount:.2f}")
    y -= 25

    pdf.setFont("Courier-Bold", 13)
    pdf.drawRightString(width - 60, y, f"Grand Total: Rs {round(grand_total,2):.2f}")

    conn.close()

    # ===== FOOTER =====
    y -= 50
    pdf.setFont("Courier", 12)
    pdf.drawCentredString(width / 2, y, "Thank you for visiting ❤️")
    y -= 20
    pdf.drawCentredString(width / 2, y, "Visit Again!")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=False,
        mimetype="application/pdf"
    )


from flask import redirect
import urllib.parse
import sqlite3

@app.route('/send-whatsapp/<int:order_id>')
def send_whatsapp(order_id):
    # check order exists
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return "Order ID not found", 404  # avoids 500

    phone = "91XXXXXXXXXX" # 👈 real number
    message = f"Your bill is ready 🧾\nCheck here:\nhttps://smart-restaurant-1-3alo.onrender.com/bill/{order_id}"
    message_encoded = urllib.parse.quote(message)
    url = f"https://wa.me/{phone}?text={message_encoded}"
    return redirect(url)

# ======================= REPORTS =======================

import sqlite3
@app.route("/admin/sales-report")
def sales_report():
    # optional query param: ?period=daily|weekly|monthly|all
    period = request.args.get('period', 'all')

    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()

    if period == 'daily':
        cur.execute("SELECT id, items, total, status, created_at FROM orders WHERE status='PAID' AND date(created_at)=date('now')")
    elif period == 'weekly':
        cur.execute("SELECT id, items, total, status, created_at FROM orders WHERE status='PAID' AND date(created_at) >= date('now','-6 days')")
    elif period == 'monthly':
        cur.execute("SELECT id, items, total, status, created_at FROM orders WHERE status='PAID' AND strftime('%Y-%m', created_at)=strftime('%Y-%m','now')")
    else:
        cur.execute("SELECT id, items, total, status, created_at FROM orders WHERE status='PAID'")

    rows = cur.fetchall()

    # normalize rows into dicts: {'id','items','total','status','created_at'}
    rows_norm = []
    for r in rows:
        if len(r) >= 5:
            rid, items_raw, total_val, status_val, created_at = r[0], r[1], r[2], r[3], r[4]
        else:
            rid, items_raw, total_val, status_val, created_at = r[0], r[1], r[2], r[3], None
        try:
            items_parsed = json.loads(items_raw) if items_raw else []
        except Exception:
            items_parsed = []
        rows_norm.append({'id': rid, 'items': items_parsed, 'total': total_val, 'status': status_val, 'created_at': created_at})

    total_sales = sum((r['total'] or 0) for r in rows_norm)
    total_orders = len(rows_norm)

    dish_count = {}
    for r in rows_norm:
        items = r['items'] or []
        for i in items:
            name = i.get('name') if isinstance(i, dict) else str(i)
            qty = int(i.get('qty', 0)) if isinstance(i, dict) else 0
            dish_count[name] = dish_count.get(name, 0) + qty

    most_ordered = max(dish_count, key=dish_count.get) if dish_count else "None"
    conn.close()

    return render_template(
        "sales_report.html",
        sales=rows_norm,
        total_sales=total_sales,
        total_orders=total_orders,
        most_ordered=most_ordered,
        period=period
    )


# ========== MENU CRUD for Admin ==========

from flask import render_template

@app.route("/menu")
def user_menu():
    return render_template("user_menu.html")


@app.route('/admin/menu-manager')
def menu_manager_page():
    if not session.get('admin'):
        return redirect('/admin/login')
    items = Menu.query.all()
    return render_template('menu_manager.html', items=items)
    
@app.route('/api/orders')
def get_orders():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT id, table_no, total, status FROM orders ORDER BY id DESC")
    rows = cur.fetchall()

    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "table_no": r[1],
            "total": r[2],
            "status": r[3]
        })

    conn.close()
    return jsonify(orders)



@app.route('/api/admin/menu', methods=['GET'])
def api_get_menu():
    items = Menu.query.order_by(Menu.id).all()
    return jsonify([{'id': i.id, 'name': i.name, 'category': i.category, 'price': i.price} for i in items])


@app.route('/api/admin/menu', methods=['POST'])
def api_add_menu():
    data = request.get_json(force=True)
    name = data.get('name')
    category = data.get('category')
    price = float(data.get('price') or 0)
    m = Menu(name=name, category=category, price=price)
    db.session.add(m)
    db.session.commit()
    # broadcast to connected clients that a menu item was added
    try:
        item_data = {'id': m.id, 'name': m.name, 'category': m.category, 'price': m.price}
        socketio.emit('menu_changed', {'action': 'add', 'item': item_data}, broadcast=True)
    except Exception:
        pass
    return jsonify(success=True, id=m.id)


@app.route('/api/admin/menu/<int:item_id>', methods=['PUT'])
def api_edit_menu(item_id):
    data = request.get_json(force=True)
    m = Menu.query.get_or_404(item_id)
    m.name = data.get('name', m.name)
    m.category = data.get('category', m.category)
    try:
        m.price = float(data.get('price', m.price))
    except Exception:
        pass
    db.session.commit()
    try:
        item_data = {'id': m.id, 'name': m.name, 'category': m.category, 'price': m.price}
        socketio.emit('menu_changed', {'action': 'edit', 'item': item_data}, broadcast=True)
    except Exception:
        pass
    return jsonify(success=True)


@app.route('/api/admin/menu/<int:item_id>', methods=['DELETE'])
def api_delete_menu(item_id):
    m = Menu.query.get_or_404(item_id)
    try:
        deleted_id = m.id
        db.session.delete(m)
        db.session.commit()
        socketio.emit('menu_changed', {'action': 'delete', 'id': deleted_id}, broadcast=True)
    except Exception:
        # if something fails, ensure DB session is clean
        db.session.rollback()
        return jsonify(success=False), 500
    return jsonify(success=True)

# ======================= INIT =======================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_db_columns()
    socketio.run(app, host="0.0.0.0", port=5000)


    
