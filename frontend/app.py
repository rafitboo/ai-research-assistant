from flask import Flask, render_template, request, redirect, url_for, session, flash
import httpx

app = Flask(__name__)
app.secret_key = "cse471_super_secret_flask_key_bracu"

API_BASE_URL = "http://127.0.0.1:8000/api"

@app.route("/")
def index():
    if "token" not in session:
        return redirect(url_for("login"))
    
    headers = {"Authorization": f"Bearer {session['token']}"}
    stats = {
        "total_papers": 0,
        "completed_papers": 0,
        "total_projects": 0,
        "subscription_plan": "Free",
        "recent_papers": [],
        "recent_projects": []
    }
    
    try:
        response = httpx.get(f"{API_BASE_URL}/dashboard/overview", headers=headers)
        if response.status_code == 200:
            stats = response.json()
    except Exception as e:
        flash(f"Could not load dashboard stats: {str(e)}", "error")

    return render_template("dashboard.html", user=session.get("user"), stats=stats)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        try:
            response = httpx.post(f"{API_BASE_URL}/auth/login", json={"email": email, "password": password})
            if response.status_code == 200:
                data = response.json()
                session["token"] = data["token"]
                session["user"] = data["user"]
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                error_msg = response.json().get("detail", "Login failed")
                flash(error_msg, "error")
        except Exception as e:
            flash(f"Connection error: {str(e)}", "error")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role", "Researcher")
        
        try:
            response = httpx.post(f"{API_BASE_URL}/auth/register", json={
                "name": name, "email": email, "password": password, "role": role
            })
            if response.status_code == 200:
                data = response.json()
                session["token"] = data["token"]
                session["user"] = data["user"]
                flash("Registration successful!", "success")
                return redirect(url_for("index"))
            else:
                error_msg = response.json().get("detail", "Registration failed")
                flash(error_msg, "error")
        except Exception as e:
            flash(f"Connection error: {str(e)}", "error")
            
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/admin")
def admin_panel():
    if "token" not in session or session.get("user", {}).get("role") != "Admin":
        flash("Admin access restricted.", "error")
        return redirect(url_for("index"))
    
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = httpx.get(f"{API_BASE_URL}/admin/stats", headers=headers)
        if response.status_code == 200:
            admin_data = response.json()
            return render_template("admin.html", stats=admin_data["stats"], users=admin_data["users"], user=session.get("user"))
        else:
            flash("Failed to load admin stats.", "error")
            return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(port=5000, debug=True)