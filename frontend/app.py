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

@app.route("/papers")
def papers_library():
    if "token" not in session:
        return redirect(url_for("login"))
    
    headers = {"Authorization": f"Bearer {session['token']}"}
    params = {}
    for key in ["topic", "year", "author", "research_area", "search"]:
        val = request.args.get(key)
        if val:
            params[key] = val
    
    papers = []
    try:
        response = httpx.get(f"{API_BASE_URL}/papers/", headers=headers, params=params)
        if response.status_code == 200:
            papers = response.json()
    except Exception as e:
        flash(f"Error fetching papers: {str(e)}", "error")

    return render_template("papers.html", user=session.get("user"), papers=papers, filters=request.args)


@app.route("/papers/upload", methods=["POST"])
def upload_paper_route():
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"}
    
    data = {
        "title": request.form.get("title"),
        "author": request.form.get("author"),
        "year": request.form.get("year") or None,
        "topic": request.form.get("topic"),
        "research_area": request.form.get("research_area"),
        "tags": request.form.get("tags")
    }
    
    files = None
    if "file" in request.files and request.files["file"].filename != "":
        file_obj = request.files["file"]
        files = {"file": (file_obj.filename, file_obj.stream.read(), file_obj.content_type)}

    try:
        response = httpx.post(f"{API_BASE_URL}/papers/upload", headers=headers, data=data, files=files)
        if response.status_code == 200:
            flash("Paper uploaded successfully to your library!", "success")
        else:
            err = response.json().get("detail", "Upload failed")
            flash(f"Upload failed: {err}", "error")
    except Exception as e:
        flash(f"Error uploading paper: {str(e)}", "error")

    return redirect(url_for("papers_library"))


@app.route("/papers/<int:paper_id>/file")
def download_paper(paper_id):
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        backend_res = httpx.get(f"{API_BASE_URL}/papers/{paper_id}/file", headers=headers)
        if backend_res.status_code == 200:
            from flask import Response
            return Response(
                backend_res.content,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"inline; filename=paper_{paper_id}.pdf"}
            )
        else:
            flash("PDF file not found or unavailable.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("papers_library"))

if __name__ == "__main__":
    app.run(port=5000, debug=True)