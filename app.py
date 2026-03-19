from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "auction_secret"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- WINNER CHECK FUNCTION ----------------
def check_winner():
    with sqlite3.connect("auction.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, end_time FROM items WHERE winner IS NULL")
        items = cur.fetchall()

        for item in items:
            item_id = item[0]
            end_time = datetime.strptime(item[1], "%Y-%m-%dT%H:%M")

            if datetime.now() > end_time:
                cur.execute("SELECT bidder, MAX(amount) FROM bids WHERE item_id=?", (item_id,))
                winner_data = cur.fetchone()
                if winner_data[0]:
                    cur.execute("UPDATE items SET winner=? WHERE id=?", (winner_data[0], item_id))
        conn.commit()

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        with sqlite3.connect("auction.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            existing_user = cur.fetchone()

            if existing_user:
                error = "Username already exists! Choose another 🛑"
            else:
                cur.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password))
                conn.commit()
                return redirect("/login")

    return render_template("register.html", error=error)


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with sqlite3.connect("auction.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cur.fetchone()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect("/dashboard")

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    check_winner()  # Auto winner update

    search = request.args.get("search", "")
    category = request.args.get("category", "")

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    query = "SELECT * FROM items WHERE name LIKE ?"
    values = ("%" + search + "%",)

    if category and category != "All":
        query += " AND category=?"
        values += (category,)

    cur.execute(query, values)
    items = cur.fetchall()
    cur.execute("SELECT * FROM items")
    items=cur.fetchall()
    conn.close()

    return render_template("dashboard.html", items=items)

# ---------------- ITEM PAGE + BID ----------------
@app.route("/item/<int:id>", methods=["GET", "POST"])
def item_page(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    # Get item
    cur.execute("SELECT * FROM items WHERE id=?", (id,))
    item = cur.fetchone()

    # Auction End Time
    end_time = datetime.strptime(item[7], "%Y-%m-%dT%H:%M")

    # If auction ended → redirect winner page
    if datetime.now() > end_time:
        conn.close()
        return redirect(f"/winner/{id}")

    # If bid submitted
    if request.method == "POST":
        bid_amount = int(request.form["amount"])

        # Bid must be higher than current highest bid
        if bid_amount > item[5]:

            # Update highest bid
            cur.execute("UPDATE items SET highest_bid=? WHERE id=?",
                        (bid_amount, id))

            # Insert bid record
            cur.execute("""
                INSERT INTO bids(item_id,bidder,amount,time)
                VALUES(?,?,?,?)
            """, (
                id,
                session["user"],
                bid_amount,
                datetime.now().strftime("%d-%m-%Y %H:%M")
            ))

            conn.commit()

    # Fetch bid history
    cur.execute("""
        SELECT * FROM bids 
        WHERE item_id=? 
        ORDER BY amount DESC
    """, (id,))
    bids = cur.fetchall()

    conn.close()

    return render_template("item.html", item=item, bids=bids)


# ---------------- MY BIDS ----------------
@app.route("/mybids", methods=["GET", "POST"])
def mybids():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    # ---------------- PLACE NEW BID ----------------
    if request.method == "POST":
        item_id = request.form["item_id"]
        bid_amount = request.form["amount"]
        user = session["user"]

        # Get item details
        cur.execute("SELECT highest_bid FROM items WHERE id=?", (item_id,))
        item = cur.fetchone()

        if item and int(bid_amount) > int(item[0]):
            # Update highest bid
            cur.execute(
                "UPDATE items SET highest_bid=? WHERE id=?",
                (bid_amount, item_id)
            )

            # Insert into bids table
            cur.execute("""
                INSERT INTO bids(item_id, bidder, amount, time)
                VALUES (?, ?, ?, ?)
            """, (
                item_id,
                user,
                bid_amount,
                datetime.now().strftime("%d-%m-%Y %H:%M")
            ))

            conn.commit()

    # ---------------- SHOW ALL ITEMS FOR DROPDOWN ----------------
    cur.execute("SELECT id, name FROM items")
    items = cur.fetchall()

    # ---------------- SHOW USER BID HISTORY ----------------
    cur.execute("""
        SELECT items.name, bids.amount, bids.time
        FROM bids
        JOIN items ON bids.item_id = items.id
        WHERE bids.bidder=?
        ORDER BY bids.id DESC
    """, (session["user"],))

    bids = cur.fetchall()

    conn.close()

    return render_template("mybids.html", bids=bids, items=items)



# ---------------- MY WINS ----------------
@app.route("/mywins")
def mywins():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    # Fetch items won by this user
    cur.execute("""
        SELECT name, highest_bid, image, category, end_time
        FROM items
        WHERE winner=?
    """, (user,))

    wins = cur.fetchall()
    conn.close()

    return render_template("mywins.html", wins=wins)


# ---------------- FEEDBACK ----------------
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        rating = request.form["rating"]
        review = request.form["review"]
        with sqlite3.connect("auction.db") as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO feedback(username,rating,review) VALUES(?,?,?)",
                        (session["user"], rating, review))
            conn.commit()
        return redirect("/dashboard")
    return render_template("feedback.html")

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["admin"] = True
            return redirect("/admin/dashboard")
    return render_template("admin/admin_login.html")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM items")
    items = cur.fetchall()

    conn.close()

    return render_template("admin/admin_dashboard.html", items=items)

# ---------------- ADMIN ADD ITEM ----------------
@app.route("/admin/add", methods=["GET", "POST"])
def admin_add():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        description = request.form["description"]
        price = request.form["price"]
        end_time = request.form["end_time"]

        image = request.files["image"]
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = sqlite3.connect("auction.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO items(name,category,description,start_price,highest_bid,image,end_time,winner)
        VALUES(?,?,?,?,?,?,?,NULL)
        """, (name, category, description, price, price, filename, end_time))

        conn.commit()
        conn.close()

        return redirect("/admin/dashboard")

    return render_template("admin/add_item.html")


#------------------winner-----------------
@app.route("/winner/<int:item_id>")
def winner(item_id):

    conn = sqlite3.connect("auction.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT name, highest_bid, winner
        FROM items
        WHERE id=?
    """, (item_id,))

    item = cur.fetchone()
    conn.close()

    return render_template("winner.html", item=item)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
