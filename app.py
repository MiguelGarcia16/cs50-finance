import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get user's stocks.
    stocks = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0 ORDER BY symbol;",
                        session["user_id"])

    # Calculate total portfolio value.
    portfolio = []
    portfolio_value = 0

    # For each stock:
    for stock in stocks:
        # Lookup current price.
        current_stock = lookup(stock["symbol"])
        if current_stock is None:
            return apology("Stock not found.")

        # Compute each stock's price, number of shares and total value.
        price = current_stock["price"]
        shares = stock["total_shares"]
        total = price * shares

        # Calculate user's net worth.
        portfolio_value += total

        # Store info in portfolio.
        portfolio.append({"symbol": stock["symbol"],
                         "shares": shares, "price": price, "total": total})

    # Get user's cash.
    row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = row[0]["cash"]

    # Calculate user's net worth.
    net_worth = portfolio_value + cash

    # Send everything to template.
    return render_template("index.html", portfolio=portfolio, cash=cash, total=net_worth)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST.
    if request.method == "POST":

        # Get form data.
        symbol = request.form.get("symbol").strip().upper()
        shares_input = request.form.get("shares")

        # Validate symbol.
        if not symbol:
            return apology("Please submit a valid stock.")

        # Validate shares.
        if not shares_input:
            return apology("Please submit a valid number of shares to buy.")

        try:
            shares = int(shares_input)
        except ValueError:
            return apology("Number of shares must be an integer.")

        if shares <= 0:
            return apology("Number of shares must be positive.")

        # Get current price.
        stock = lookup(symbol)
        if stock is None:
            return apology("Stock not found.")

        # Calculate cost of transaction.
        total_cost = shares * stock["price"]

        # Get user's cash.
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]["cash"]

        # Note: "rows" always stores a list of dictionaries, even if it is comprised of only one result.

        if total_cost > cash:
            return apology("Insufficient funds to complete transaction.")

        # Execute transaction.
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?);", session["user_id"],
                   symbol, shares, stock["price"])

        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total_cost, session["user_id"])

        # Redirect to homepage.
        flash("Stock bought successfully!")
        return redirect("/")

    # User reached route via GET.
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Get transaction history.
    history = db.execute("SELECT symbol, shares, price, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC;",
                         session["user_id"])
    if not history:
        return apology("No transactions have been made.")

    # Render template.
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST.
    if request.method == "POST":

        # Get form data.
        symbol = request.form.get("symbol")

        # Validate symbol.
        if not symbol:
            return apology("Please submit a valid stock.")

        stock = lookup(symbol)
        if stock is None:
            return apology("Stock not found.")

        # Display result page.
        return render_template("quoted.html", stock=stock)

    # User reached route via GET.
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST.
    if request.method == "POST":

        # Get form data.
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate username.
        if not username:
            return apology("Please submit a valid username.")

        # Validate password.
        if not password:
            return apology("Please submit a valid password.")

        # Validate confirmation.
        if not confirmation:
            return apology("Please confirm your password.")

        if password != confirmation:
            return apology("Passwords do not match.")

        # Hash user's password.
        hashed_pw = generate_password_hash(password)

        # Note: A try/except block is more robust as a method for checking data integrity, as the database
        # already handles "username" duplication through a "UNIQUE INDEX". As a rule of thumb, the validation
        # logic is the responsibility of the programmer, while the data integrity should be handled by the
        # database.

        # Store user in the database.
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_pw)
        except Exception:
            return apology("Username already exists.")

        # Redirect user to login page.
        flash("User registered successfully!")
        return redirect("/login")

    # User reached route via GET.
    else:
        # Render template of the register page.
        return render_template("register.html")


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    """Change user's registered password"""

    # User reached route via POST.
    if request.method == "POST":

        # Get form data.
        current_password = request.form.get("pass_old")
        password_new = request.form.get("pass_new")
        confirmation = request.form.get("confirm_new")

        # Get user's current password.
        stored_hash = db.execute("SELECT hash FROM users WHERE id = ?;", session["user_id"])

        # Validate data.
        if len(stored_hash) != 1:
            return apology("User not found.")
        if not current_password:
            return apology("Please submit your current password.")
        if not check_password_hash(stored_hash[0]["hash"], current_password):
            return apology("Incorrect password.")
        if not password_new:
            return apology("Please submit a new, valid password.")
        if not confirmation:
            return apology("Please confirm your new password.")
        if password_new != confirmation:
            return apology("New password does not match confirmed password.")
        if check_password_hash(stored_hash[0]["hash"], password_new):
            return apology("New password must be different from current password.")

        # Hash new password.
        new_hash = generate_password_hash(password_new)

        # Replace stored hash on server.
        db.execute("UPDATE users SET hash = ? WHERE id = ?;", new_hash, session["user_id"])
        flash("Password changed sucessfully!")
        return redirect("/")

    # User reached route via GET.
    else:
        return render_template("change.html")


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    """Add the ability to reinforce user funds"""

    # User reached route via "POST".
    if request.method == "POST":

        # Define a deposit limit.
        deposit_limit = 10000

        # Get form data.
        money = request.form.get("money")
        action = request.form.get("action")

        # Check input for money.
        if not money:
            return apology("Please insert an integer.")

        # Convert money into an int.
        try:
            money = int(money)
        except ValueError:
            return apology("Quantity of money inserted must be an integer.")

        # Validate money.
        if money <= 0:
            return apology("Quantity of money inserted must be a positive integer.")

        # Validate action.
        allowed_actions = ["withdraw", "deposit"]
        if action not in allowed_actions:
            return apology("Error processing transaction.")

        # Get user's current funds.
        row = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])

        # Process a withdrawal.
        if action == "withdraw":
            if row[0]["cash"] < money:
                return apology("You do not have enough funds.")
            else:
                db.execute("UPDATE users SET cash = cash - ? WHERE id = ?;",
                           money, session["user_id"])
                flash("Transaction successful!")
                return redirect("/")

        # Process a deposit.
        if action == "deposit":
            if money > deposit_limit:
                return apology("Deposit limit is 10 000$.")
            else:
                db.execute("UPDATE users SET cash = cash + ? WHERE id = ?;",
                           money, session["user_id"])
                flash("Transaction successful!")
                return redirect("/")

    # User reached route via "GET".
    else:
        return render_template("transfer.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST.
    if request.method == "POST":

        # Get form data.
        symbol = request.form.get("symbol")
        shares_input = request.form.get("shares")

        # Validate symbol.
        if not symbol:
            return apology("Please submit a valid stock.")

        # Normalize symbol.
        symbol = symbol.strip().upper()

        # Validate shares.
        if not shares_input:
            return apology("Please submit a valid number of shares to sell.")

        try:
            shares = int(shares_input)
        except ValueError:
            return apology("Number of shares must be an integer.")

        if shares <= 0:
            return apology("Number of shares must be positive.")

        # Check user's ownership of stock.
        rows = db.execute("SELECT SUM(shares) AS total_shares FROM transactions WHERE user_id = ? AND symbol = ?;",
                          session["user_id"], symbol)

        if len(rows) != 1 or rows[0]["total_shares"] is None:
            return apology("Invalid stock.")

        owned_shares = rows[0]["total_shares"]

        if owned_shares < shares:
            return apology("You do not have enough shares to sell.")

        # Get stock's current price.
        stock = lookup(symbol)
        if stock is None:
            return apology("Stock not found.")

        # Calculate cost of transaction.
        total_cost = shares * stock["price"]

        # Execute transaction.
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?);", session["user_id"],
                   symbol, -shares, stock["price"])

        # Update user's cash.
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total_cost, session["user_id"])

        # Redirect to homepage.
        flash("Stock sold successfully!")
        return redirect("/")

    # User reached route via GET.
    else:
        stocks = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0 ORDER BY symbol;",
                            session["user_id"])

        return render_template("sell.html", stocks=stocks)
