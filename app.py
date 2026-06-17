from flask import (Flask,
                   render_template,
                   request,
                   make_response,
                   redirect,
                   url_for,
                   session,
                   flash,)
from product import (products as pro,
                     get_product_by_category,
                     get_product_by_id,
                     update_stock)
import json, random, os, uuid
import requests
from werkzeug.utils import secure_filename
app = Flask(__name__)
app.secret_key = "your_secret_key"  # needed for flash messages

# ==============================================================================
# USERS
# ==============================================================================
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ==============================================================================
# ORDERS
# ==============================================================================
ORDERS_FILE = "orders.json"
def save_order(order):
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
    else:
        orders = []

    orders.append(order)

    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)

def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            return json.load(f)
    return []

# ==============================================================================
# TELEGRAM BOT FUNCTION
# ==============================================================================
TELEGRAM_TOKEN = "8321967454:AAG4oEJUxN3jEAzznhwh1T1o__M9Wsppicc"
CHAT_ID = -1004420539883

# ==============================================================================
# TELEGRAM BOT NOTIFICATIONS
# ==============================================================================
EXCHANGE_RATE = 4100  # 1 USD = 4100 KHR

def send_order_to_telegram(order):

    text = f"""
🛒 *NEW ORDER RECEIVED*

━━━━━━━━━━━━━━━

📦 *Order ID:* `#{order['order_id']}`

👤 *Customer Information*
• Name: {order['customer_name']}
• Phone: {order['phone']}
• Email: {order['email']}

📍 *Delivery Address*
{order['address']}

💳 *Payment Method:* {order['payment_method'].upper()}

━━━━━━━━━━━━━━━

🛍 *ORDER ITEMS*
"""

    for index, item in enumerate(order["items"], start=1):
        line_total = item["discountedPrice"] * item["qty"]

        size_text = f" ({item['size']})" if item.get("size") else ""

        text += (
            f"\n{index}. *{item['title']}{size_text} x {item['qty']}*\n"
            f"   Total: ${line_total:.2f}\n"
        )

    shipping_text = (
        "FREE"
        if order["shipping"] == 0
        else f"${order['shipping']:.2f}"
    )

    text += f"""
━━━━━━━━━━━━━━━

💰 *ORDER SUMMARY*

Subtotal: ${order['subtotal']:.2f}
Shipping: {shipping_text}
*Grand Total:* ${order['total']:.2f} | ៛{order['total'] * EXCHANGE_RATE:,.0f}

━━━━━━━━━━━━━━━

🕒 *Status:* Pending

🌸 *LA BEAUTÉ STUDIO* 🌸
Thank you for your order, and we can't wait to serve you again.
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=5
        )

        print("Telegram Status:", r.status_code)
        print("Telegram Response:", r.text)

        return r.ok

    except Exception as e:
        print("Telegram Error:", e)

        return False

# ==============================================================================
# HOME PAGE
# ==============================================================================
@app.get('/')
def home():  # put application's code here
    return render_template('front/index.html', products=pro)

@app.get('/products')
def products():  # put application's code here
    return render_template('front/products.html', products=pro)

@app.get('/product/<int:id>')
def product(id):
    from product import get_product_by_id, get_product_by_category
    product = get_product_by_id(id)
    if not product:
        return "Product not found", 404
    related_product = get_product_by_category(product['category'], product['_id'])

    return render_template(
        'front/product.html',
        product=product,
        related_product=related_product,
    )

# ==============================================================================
# CART
# ==============================================================================
@app.route("/cart")
def cart():
    data = get_cart_data()
    return render_template("front/cart.html",**data)

@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    product_id = int(request.form.get("product_id"))
    quantity = int(request.form.get("quantity", 1))

    size = request.form.get("size")
    if not size:
        flash("Please select a size.", "danger")
        return redirect(request.referrer)

    from product import get_product_by_id
    product = get_product_by_id(product_id)

    if not product:
        return "Product not found", 404

    if quantity > product["stock"]:
        flash(
            f"Only {product['stock']} items available.",
            "danger"
        )
        return redirect(request.referrer)

    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []

    found = False

    for item in cart_products:
        if (
                item["_id"] == product["_id"]
                and item.get("size") == size
        ):
            new_qty = item["qty"] + quantity

            if new_qty > product["stock"]:
                flash(
                    f"Only {product['stock']} items available.",
                    "danger"
                )

                return redirect(request.referrer)

            item["qty"] = new_qty
            found = True
            break

    if not found:
        cart_products.append({
            "_id": product["_id"],
            "title": product["title"],
            "category": product["category"],
            "price": product["price"],
            "qty": quantity,
            "size": size,
            "brand": product["brand"],
            "image": product["image"]
        })

    resp = make_response(redirect("/cart"))
    resp.set_cookie("cart_list", json.dumps(cart_products))
    return resp

@app.context_processor
def inject_cart_count():
    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []

    count = sum(item.get("qty", 1) for item in cart_products)

    return dict(cart_count=count)

@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = request.cookies.get("cart_list")
    if cart:
        cart_items = json.loads(cart)
        cart_items = [item for item in cart_items if item["_id"] != product_id]

        resp = redirect(url_for("cart"))
        resp.set_cookie("cart_list", json.dumps(cart_items))
        return resp

    return redirect(url_for("cart"))

@app.route('/cart/increase/<int:product_id>')
def increase_cart(product_id):
    from product import get_product_by_id
    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []
    product = get_product_by_id(product_id)

    for item in cart_products:
        if item["_id"] == product_id:

            if item["qty"] < product["stock"]:
                item["qty"] += 1
                break

    resp = make_response(redirect('/cart'))
    resp.set_cookie("cart_list", json.dumps(cart_products))
    return resp

@app.route('/cart/decrease/<int:id>')
def decrease_cart(id):

    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []

    for item in cart_products:
        if item["_id"] == id and item["qty"] > 1:
            item["qty"] -= 1
            break

    resp = make_response(redirect('/cart'))
    resp.set_cookie("cart_list", json.dumps(cart_products))
    return resp

@app.route('/cart/remove/<int:id>')
def remove_cart(id):

    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []

    cart_products = [
        item for item in cart_products
        if item["_id"] != id
    ]

    resp = make_response(redirect('/cart'))
    resp.set_cookie("cart_list", json.dumps(cart_products))

    return resp

# ==============================================================================
# SHIPPING CALCULATION X HELPER FUNCTION
# ==============================================================================
def calculate_shipping(subtotal):
    if subtotal == 0:
        return 0
    elif subtotal < 100:
        return 5
    elif subtotal < 300:
        return 3
    else:
        return 0

# Add Helper Functions
def get_cart_data():
    from product import get_product_by_id

    cart_cookie = request.cookies.get("cart_list")
    cart_products = json.loads(cart_cookie) if cart_cookie else []

    subtotal = 0
    total_items = 0

    for item in cart_products:

        product = get_product_by_id(item["_id"])

        if product:
            item["stock"] = product.get("stock", 0)
            item["discountedPrice"] = product.get(
                "discountedPrice",
                product["price"]
            )
            subtotal += item["discountedPrice"] * item["qty"]
            total_items += item["qty"]

    shipping = calculate_shipping(subtotal)

    return {
        "cart_products": cart_products,
        "subtotal": subtotal,
        "total_items": total_items,
        "shipping": shipping
    }

# ==============================================================================
# CHECKOUT PROCESS
# ==============================================================================
@app.route("/checkout")
def checkout():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    users = load_users()
    logged_in_user = next((u for u in users if u["id"] == session["user_id"]), None)

    if not logged_in_user:
        flash("User not found. Please login again.", "danger")
        return redirect(url_for("login"))

    data = get_cart_data()

    if not data["cart_products"]:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("cart"))

    return render_template("front/orders/checkout.html", user=logged_in_user, **data)


@app.route("/checkout/confirm", methods=["POST"])
def checkout_confirm():
    # Require login
    if "user_id" not in session:
        flash("You must login or register before placing an order.", "danger")
        return redirect(url_for("login"))

    # Get logged-in user from session
    users = load_users()
    logged_in_user = next((u for u in users if u["id"] == session["user_id"]), None)

    if not logged_in_user:
        flash("User not found. Please login again.", "danger")
        return redirect(url_for("login"))

    # Billing form data
    name = request.form.get("name")
    phone = request.form.get("phone")
    email = request.form.get("email")
    address = request.form.get("address")
    payment_method = request.form.get("payment_method")

    # Compare billing email with logged-in user's email
    if email != logged_in_user["email"]:
        flash("Incorrect email in Billing Details. Please use your account email.", "danger")
        return redirect(url_for("checkout"))

    # Cart data
    data = get_cart_data()
    if not data["cart_products"]:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("cart"))
    total = data["subtotal"] + data["shipping"]

    order_id = random.randint(100000, 999999)
    order = {
        "order_id": order_id,
        "customer_name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "payment_method": payment_method,
        "items": data["cart_products"],
        "subtotal": data["subtotal"],
        "shipping": data["shipping"],
        "total": total,
        "status": "Processing"
    }

    # Check stock first
    for item in data["cart_products"]:

        product = get_product_by_id(item["_id"])

        if not product:
            flash("Product not found.", "danger")
            return redirect(url_for("cart"))

        if item["qty"] > product["stock"]:
            flash(
                f"{product['title']} only has {product['stock']} left in stock.",
                "danger"
            )
            return redirect(url_for("cart"))

    save_order(order)

    # Reduce stock
    for item in data["cart_products"]:
        update_stock(
            item["_id"],
            item["qty"]
        )

    send_order_to_telegram(order)

    resp = make_response(
        render_template("front/orders/order_success.html",
                        customer_name=name,
                        order_id=order_id,
                        **data,
                        total=total)
    )
    resp.set_cookie("cart_list", json.dumps([]))
    return resp


@app.route('/order_success/<int:order_id>')
def order_success(order_id):
    return render_template("front/orders/order_success.html", order_id=order_id)

@app.route('/orders/<int:order_id>')
def order_receipt(order_id):
    orders = load_orders()
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return "Order not found", 404
    return render_template("front/orders/order_receipt.html", order=order)

@app.route('/orders')
def orders():
    orders = load_orders()
    return render_template("front/orders/orders_history.html", orders=orders)


# ==============================================================================
# USER PROFILE
# ==============================================================================
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "profile")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the folder exists at startup
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_user_ids():
    users = load_users()
    changed = False
    for u in users:
        if "id" not in u:
            u["id"] = str(uuid.uuid4())
            changed = True
    if changed:
        save_users(users)
# ==============================================================================
@app.route("/account")
def account():
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to access your account.", "danger")
        return redirect(url_for("login"))

    # Load users and find the logged-in one
    users = load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)

    if not user:
        flash("User not found. Please login again.", "danger")
        return redirect(url_for("login"))

    orders = load_orders()
    active_orders = [o for o in orders if o.get("status") and o["status"] != "Delivered"]
    saved_items = []

    return render_template(
        "front/account.html",
        user=user,
        orders=orders,
        active_orders=active_orders,
        saved_items=saved_items
    )

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Basic validation
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("create_user"))

        users = load_users()

        # Check if username/email already exists
        if any(u["username"] == username for u in users):
            flash("Username already taken!", "danger")
            return redirect(url_for("create_user"))
        if any(u["email"] == email for u in users):
            flash("Email already registered!", "danger")
            return redirect(url_for("create_user"))

        # Save new user (plain password)
        new_user = {
            "id": str(uuid.uuid4()),  # unique ID
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
            "password": password  # stored as plain text
        }
        users.append(new_user)
        save_users(users)

        flash("User created successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template('front/user/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        users = load_users()
        user = next((u for u in users if u["username"] == username), None)

        if not user:
            flash("Username not found!", "danger")
            return redirect(url_for("login"))

        if user["password"] != password:
            flash("Incorrect password!", "danger")
            return redirect(url_for("login"))

        # Successful login → store in session
        session["user_id"] = user["id"]

        flash(f"Welcome back, {user['full_name']}!", "success")
        return redirect(url_for("account"))  # go straight to account

    return render_template("front/user/login.html")

@app.route("/upload-profile", methods=["POST"])
def upload_profile():
    if "profile_image" not in request.files:
        flash("No file part", "danger")
        return redirect(url_for("account"))

    file = request.files["profile_image"]
    if file.filename == "":
        flash("No selected file", "danger")
        return redirect(url_for("account"))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        # Ensure folder exists before saving
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(filepath)

        # Update user record
        users = load_users()
        user = users[-1]  # for now, last registered user
        user["profile_image"] = filename
        save_users(users)

        flash("Profile image updated!", "success")
    else:
        flash("Invalid file type", "danger")

    return redirect(url_for("account"))

@app.route("/edit-profile", methods=["POST"])
def edit_profile():
    full_name = request.form.get("full_name")
    username = request.form.get("username")
    email = request.form.get("email")
    phone = request.form.get("phone")
    address = request.form.get("address")

    users = load_users()
    user = users[-1]  # for now, last registered user

    # Update fields
    user["full_name"] = full_name
    user["username"] = username
    user["email"] = email
    user["phone"] = phone
    user["address"] = address

    save_users(users)

    flash("Profile updated successfully!", "success")
    return redirect(url_for("account"))

@app.route("/logout")
def logout():
    # Clear all session data
    session.clear()

    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        users = load_users()
        user = next((u for u in users if u["email"] == email), None)

        if not user:
            flash("No account found with that email.", "danger")
            return redirect(url_for("forgot_password"))

        # Instead of sending email, just redirect to reset page
        token = "dummy-token"  # in real app, generate secure token
        return redirect(url_for("reset_password", token=token))

    return render_template("front/user/forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    users = load_users()
    user = users[-1]  # replace with lookup by token

    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("reset_password", token=token))

        user["password"] = new_password
        save_users(users)

        flash("Password reset successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("front/user/reset_password.html", token=token)


# @app.get('/test')
# def test():  # put application's code here
#     fruits = ['apple', 'pear', 'orange', 'banana']
#     return render_template('test.html', fruits=fruits, hour=10)

if __name__ == '__main__':
    app.run()
