# ---------------- Standard Library ----------------
from io import BytesIO
from datetime import datetime
from flask import send_from_directory, render_template
import requests

# ---------------- Third-party Packages ----------------
import pandas as pd
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet


# ====================================================
# Flask App & Config
# ====================================================
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # ⚠️ Change in production!

# ---------------- Database Config ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://root:Da1wi2d$@localhost/umuhuza"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- Email Config ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "oniyonkuru233@gmail.com"
app.config['MAIL_PASSWORD'] = "jvvd hzba fwqa jbnz"  # ⚠️ Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = "oniyonkuru233@gmail.com"
mail = Mail(app)

# ====================================================
# Database Models
# ====================================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    role = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class MarketPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commodity = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    province = db.Column(db.String(100), nullable=True)  # New column
    date = db.Column(db.Date, nullable=False)
    unit = db.Column(db.String(20), nullable=True)

    

# ====================================================
# Flask-Login Config
# ====================================================
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ====================================================
# Token Serializer for Password Reset
# ====================================================
serializer = URLSafeTimedSerializer(app.secret_key)

# ====================================================
# Routes
# ====================================================

# -------- General Pages --------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about-us')
def about_us():
    return render_template('about-us.html')

# Keep legacy dash route
@app.route('/dash')
def dash():
    return render_template('dash.html')

# ====================================================
# Authentication
# ====================================================
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone")
        email = request.form.get("email")
        role = request.form.get("role")
        password = request.form.get("password")

        user = None
        if phone:
            user = User.query.filter_by(phone=phone, role=role).first()
        elif email:
            user = User.query.filter_by(email=email, role=role).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "error")

    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        full_name = request.form.get('fullName')
        phone = request.form.get('phone')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('create_account'))

        if User.query.filter((User.phone == phone) | (User.email == email)).first():
            flash("Phone or Email already registered.", "error")
            return redirect(url_for('create_account'))

        new_user = User(full_name=full_name, phone=phone, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('create-account.html')

# ====================================================
# Password Reset
# ====================================================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Your email is not registered.", "error")
            return redirect(url_for("forgot_password"))

        token = serializer.dumps(email, salt="password-reset-salt")
        reset_link = url_for("reset_password", token=token, _external=True)

        try:
            msg = Message(
                subject="Password Reset Request - UMUHUZA",
                recipients=[email],
                body=f"""
Hello {user.full_name},

You requested a password reset for your UMUHUZA account.
Click the link below to reset your password:

{reset_link}

This link will expire in 30 minutes.

If you did not request this, please ignore this email.

- UMUHUZA Team
"""
            )
            mail.send(msg)
            flash("Password reset link has been sent to your email.", "success")
        except Exception as e:
            flash(f"Error sending email: {str(e)}", "error")

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=1800)
    except SignatureExpired:
        flash("The reset link has expired. Please try again.", "error")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid reset link.", "error")
        return redirect(url_for("forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Invalid email in reset link.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirmPassword")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password", token=token))

        user.set_password(password)
        db.session.commit()
        flash("Your password has been reset successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# ====================================================
# Dashboard (Role-Based)
# ====================================================
@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role

    if role == "farmer":
        # ---- Weather API (Open-Meteo) ----
        lat, lon = -1.94, 30.06  # Kigali coordinates
        weather_data = {}
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
                "&timezone=Africa%2FKigali"
            )
            resp = requests.get(url, timeout=5)
            json_data = resp.json()
            weather_data = json_data.get("daily", {})
        except Exception as e:
            weather_data = {
                "temperature_2m_max": [],
                "temperature_2m_min": [],
                "precipitation_sum": [],
                "time": [],
                "error": str(e)
            }

        # ---- Market Prices (from DB) ----
        try:
            market_prices = MarketPrice.query.order_by(MarketPrice.date.desc()).all()
        except Exception as e:
            market_prices = []
            app.logger.error(f"Error fetching market prices: {e}")

        return render_template(
            "dashboards/farmer_dashboard.html",
            user=current_user,
            weather_data=weather_data,
            market_prices=market_prices
        )

    # ... other roles unchanged ...


    elif role == "promoter":
        return render_template("dashboards/promoter_dashboard.html", user=current_user)
    elif role == "dealer":
        return render_template("dashboards/dealer_dashboard.html", user=current_user)
    elif role == "processor":
        return render_template("dashboards/processor_dashboard.html", user=current_user)
    # ---------------- Researcher ----------------
    elif role == "researcher":
        try:
            # Fetch market prices from DB
            market_prices = MarketPrice.query.order_by(MarketPrice.date.desc()).all()

            # Prepare chart data
            chart_data = {"dates": [], "commodities": {}, "avg_prices": {}}

            if market_prices:
                # Extract unique sorted dates
                unique_dates = sorted(set([mp.date.strftime("%Y-%m-%d") for mp in market_prices]))
                chart_data["dates"] = unique_dates

                # Group by commodity
                commodity_prices = {}
                for mp in market_prices:
                    if mp.commodity not in commodity_prices:
                        commodity_prices[mp.commodity] = {}
                    commodity_prices[mp.commodity][mp.date.strftime("%Y-%m-%d")] = mp.price

                # Build datasets aligned with dates
                for commodity, prices_by_date in commodity_prices.items():
                    values = [prices_by_date.get(d, None) for d in unique_dates]
                    chart_data["commodities"][commodity] = values

                    # Average price
                    valid_prices = [p for p in prices_by_date.values() if p is not None]
                    chart_data["avg_prices"][commodity] = (
                        sum(valid_prices) / len(valid_prices) if valid_prices else 0
                    )
            else:
                chart_data = None

            # -------- Load NISR dataset for charts (bar + histogram) --------
            nisr_chart_data = None
            try:
                df = pd.read_excel("datasets/Tables_2025_Season_A.xlsx")

                # Average prices by commodity (bar chart)
                if "Commodity" in df.columns and "Price" in df.columns:
                    avg_prices = df.groupby("Commodity")["Price"].mean().to_dict()
                    nisr_chart_data = {
                        "commodities": list(avg_prices.keys()),
                        "avg_prices": list(avg_prices.values())
                    }

                # Histogram of prices
                if "Price" in df.columns:
                    price_series = df["Price"].dropna()
                    if not price_series.empty:
                        # Ensure numeric
                        price_series = pd.to_numeric(price_series, errors="coerce").dropna()
                        if not price_series.empty:
                            bins = pd.cut(price_series, bins=10)
                            counts = bins.value_counts(sort=False)
                            bin_labels = [f"{interval.left:.0f}-{interval.right:.0f}" for interval in counts.index]
                            if nisr_chart_data is None:
                                nisr_chart_data = {}
                            nisr_chart_data.update({
                                "histogram_bins": bin_labels,
                                "histogram_counts": counts.tolist()
                            })
            except Exception as e:
                app.logger.error(f"Error reading NISR dataset for researcher: {e}")

        except Exception as e:
            app.logger.error(f"Error preparing researcher data: {e}")
            market_prices, chart_data, nisr_chart_data = [], None, None

        return render_template(
            "dashboards/researcher_dashboard.html",
            user=current_user,
            market_prices=market_prices,
            chart_data=chart_data,
            nisr_chart_data=nisr_chart_data
        )

        return render_template("dashboards/researcher_dashboard.html", user=current_user)
    elif role == "policy":
        stats = {
            "farmers": User.query.filter_by(role="farmer").count(),
            "promoters": User.query.filter_by(role="promoter").count(),
            "dealers": User.query.filter_by(role="dealer").count(),
            "processors": User.query.filter_by(role="processor").count(),
            "researchers": User.query.filter_by(role="researcher").count(),
            "policymakers": User.query.filter_by(role="policy").count(),
        }
        return render_template("dashboards/policy_dashboard.html",
                               user=current_user, stats=stats)
    else:
        flash("Role not recognized. Contact admin.", "error")
        return redirect(url_for("login"))
    
    # ====================================================
# Researcher Dataset Download
# ====================================================

# Download route for NISR dataset
@app.route('/download/nisr_dataset')
def download_nisr_dataset():
    try:
        return send_from_directory(
            directory="datasets",
            path="Tables_2025_Season_A.xlsx",
            as_attachment=True
        )
    except Exception as e:
        app.logger.error(f"Error downloading NISR dataset: {e}")
        return "Dataset not available", 500


# Researcher Dashboard
@app.route('/researcher_dashboard')
def researcher_dashboard():
    user = {"full_name": "Researcher User"}  # Replace with actual logged-in user

    market_prices = MarketPrice.query.order_by(MarketPrice.date.desc()).all()

    # ✅ Load NISR dataset (preview + chart data)
    nisr_preview, nisr_chart_data = None, None
    try:
        df = pd.read_excel("datasets/Tables_2025_Season_A.xlsx")

        # Keep only the first 10 rows for preview
        nisr_preview = df.head(10).to_dict(orient="records")

        # Chart data: average prices per commodity
        if "Commodity" in df.columns and "Price" in df.columns:
            avg_prices = df.groupby("Commodity")["Price"].mean().to_dict()

            nisr_chart_data = {
                "commodities": list(avg_prices.keys()),
                "avg_prices": list(avg_prices.values())
            }

    except Exception as e:
        app.logger.error(f"Error reading NISR dataset: {e}")

    # Existing DB chart data
    chart_data = None
    if market_prices:
        commodities = {}
        dates = sorted(set([mp.date.strftime("%Y-%m-%d") for mp in market_prices]))
        for mp in market_prices:
            if mp.commodity not in commodities:
                commodities[mp.commodity] = {}
            commodities[mp.commodity][mp.date.strftime("%Y-%m-%d")] = mp.price

        datasets = {c: [commodities[c].get(d, None) for d in dates] for c in commodities}
        avg_prices = {c: sum(v for v in vals if v) / len([v for v in vals if v]) for c, vals in datasets.items()}
        chart_data = {"dates": dates, "commodities": datasets, "avg_prices": avg_prices}

    return render_template(
        "researcher_dashboard.html",
        user=user,
        market_prices=market_prices,
        chart_data=chart_data,
        nisr_preview=nisr_preview,
        nisr_chart_data=nisr_chart_data
    )
    
    
@app.route("/download_market_prices")
@login_required
def download_market_prices():
    if current_user.role != "researcher" and current_user.role != "policy":
        flash("Access denied. Only researchers and policymakers can download datasets.", "error")
        return redirect(url_for("dashboard"))

    try:
        prices = MarketPrice.query.order_by(MarketPrice.date.desc()).all()
    except Exception as e:
        app.logger.error(f"Error fetching market prices: {e}")
        return "No market price data available", 404

    if not prices:
        return "No market price data available", 404

    # Convert to DataFrame
    df = pd.DataFrame([{
        "ID": p.id,
        "Commodity": p.commodity,
        "Price": p.price,
        "Province": p.province,
        "Unit": p.unit,
        "Date": p.date
    } for p in prices])

    # Save to memory as CSV
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="market_prices.csv"
    )

# -------- User Listing for Policy Maker --------
@app.route('/users/<role>')
@login_required
def list_users(role):
    if current_user.role != "policy":
        flash("Access denied. Only policy makers can view user lists.", "error")
        return redirect(url_for("dashboard"))

    valid_roles = ["farmer", "promoter", "dealer", "processor", "researcher", "policy"]
    if role not in valid_roles:
        flash("Invalid role selected.", "error")
        return redirect(url_for("dashboard"))

    users = User.query.filter_by(role=role).all()
    return render_template("dashboards/user_list.html",
                           role=role.capitalize(), users=users)

# -------- Export Users (Excel & PDF) --------
@app.route('/export/<role>/<filetype>')
@login_required
def export_users(role, filetype):
    if current_user.role != "policy":
        flash("Access denied. Only policy makers can export data.", "error")
        return redirect(url_for("dashboard"))

    valid_roles = ["farmer", "promoter", "dealer", "processor", "researcher", "policy"]
    if role not in valid_roles:
        flash("Invalid role.", "error")
        return redirect(url_for("dashboard"))

    users = User.query.filter_by(role=role).all()
    data = [{
        "ID": u.id,
        "Full Name": u.full_name,
        "Phone": u.phone or "-",
        "Email": u.email or "-"
    } for u in users]

    # Excel
    if filetype == "excel":
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=f"{role.capitalize()}s")
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"{role}_users.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # PDF
    elif filetype == "pdf":
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"{role.capitalize()} Users", styles['Title']))

        table_data = [["ID", "Full Name", "Phone", "Email"]] + [
            [str(u.id), u.full_name, u.phone or "-", u.email or "-"] for u in users
        ]
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)

        doc.build(elements)
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"{role}_users.pdf",
                         mimetype="application/pdf")

    else:
        flash("Unsupported export format.", "error")
        return redirect(url_for("list_users", role=role))

# ====================================================
# Contact
# ====================================================
@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message_body = request.form.get("message")

        try:
            msg = Message(
                subject=f"New Contact Form Message from {name}",
                recipients=["oniyonkuru233@gmail.com"],
                body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_body}"
            )
            mail.send(msg)
            flash("Your message has been sent successfully!", "success")
        except Exception as e:
            flash(f"Error sending message: {str(e)}", "error")

        return redirect(url_for("contact"))

    return render_template('contact.html')

# ====================================================
# Other Informational Pages
# ====================================================
@app.route('/market')
def market():
    return render_template('market.html')

@app.route('/input')
def input_page():
    return render_template('input.html')

@app.route('/irrigation')
def irrigation():
    return render_template('irrigation.html')

@app.route('/service')
def service():
    youtube_id = "29KDeFQIIpI"
    return render_template('service.html', youtube_id=youtube_id)

@app.route('/weather')
def weather():
    return render_template('weather.html')

@app.route('/agrodealer')
def appreciate_agrodealer():
    return render_template('appreciate-agrodealer.html')

@app.route('/customer')
def appreciate_customer():
    return render_template('appreciate-customer.html')

@app.route('/farmer')
def appreciate_farmer():
    return render_template('appreciate-farmer.html')

@app.route('/policy-maker')
def appreciate_policymaker():
    return render_template('appreciate-policymaker.html')

@app.route('/promoter')
def appreciate_promoter():
    return render_template('appreciate-promoter.html')

@app.route('/research')
def appreciate_research():
    return render_template('appreciate-research.html')

# ====================================================
# Run
# ====================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)