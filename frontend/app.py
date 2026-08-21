from flask import Flask, render_template, request, redirect, url_for, session, flash
import httpx
from reading_progress_routes import reading_progress_bp

app = Flask(__name__)
app.secret_key = "cse471_super_secret_flask_key_bracu"

API_BASE_URL = "http://127.0.0.1:8000/api"

app.register_blueprint(reading_progress_bp)  

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



@app.route("/projects")
def projects_list():
    if "token" not in session:
        return redirect(url_for("login"))
    
    headers = {"Authorization": f"Bearer {session['token']}"}
    projects = []
    try:
        response = httpx.get(f"{API_BASE_URL}/projects/", headers=headers)
        if response.status_code == 200:
            projects = response.json()
    except Exception as e:
        flash(f"Error loading projects: {str(e)}", "error")

    return render_template("projects.html", user=session.get("user"), projects=projects)


@app.route("/projects/create", methods=["POST"])
def create_project_route():
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"}
    title = request.form.get("title")
    description = request.form.get("description")

    payload = {
        "title": title,
        "description": description
    }

    try:
        response = httpx.post(f"{API_BASE_URL}/projects/create", headers=headers, json=payload)
        if response.status_code == 200:
            flash(f"Project '{title}' created successfully!", "success")
        else:
            err = response.json().get("detail", "Failed to create project")
            flash(f"Error: {err}", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("projects_list"))






@app.route("/papers/<int:paper_id>/workspace")
def paper_workspace_view(paper_id):
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("paper_workspace.html", paper_id=paper_id, user=session.get("user"))



@app.route('/journal')
def journal_page():
    if "token" not in session:
            return redirect(url_for("login"))
    return render_template('journal.html')

@app.route("/literature-matrix")
def literature_matrix_view():
    if "token" not in session:
        return redirect(url_for("login"))

    return render_template(
        "literature_matrix.html",
        user=session.get("user")
    )

@app.route("/projects/<int:project_id>/literature-matrix")
def project_literature_matrix_redirect(project_id):
    return redirect(f"/literature-matrix?project_id={project_id}")

@app.route("/projects/<int:project_id>/workspace")
def project_workspace_view(project_id):
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("project_collab.html", project_id=project_id, user=session.get("user"))

@app.route("/projects/<int:project_id>/tasks")
def task_board_view(project_id):
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("task_board.html", project_id=project_id, user=session.get("user"))

@app.route("/papers/<int:paper_id>/summary")
def paper_summary_view(paper_id):
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("paper_summary.html", paper_id=paper_id, user=session.get("user"))

@app.route("/assistant")
def assistant_view():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("assistant.html", user=session.get("user"))

@app.route("/ai/titles")
def ai_titles_view():
    if "token" not in session:
        return redirect(url_for("login"))
    
    # Fetch projects so users can optionally link saved titles to projects
    headers = {"Authorization": f"Bearer {session['token']}"}
    projects = []
    try:
        res = httpx.get(f"{API_BASE_URL}/projects/", headers=headers)
        if res.status_code == 200:
            projects = res.json()
    except Exception:
        pass

    return render_template("ai_titles.html", user=session.get("user"), projects=projects)

@app.route("/literature")
def literature_review_view():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template(
        "research_gaps.html",
        user=session.get("user")
    )

@app.route("/supervision")
def supervision_portal_view():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template(
        "supervisor_portal.html",
        user=session.get("user")
    )

@app.route("/smart-folders")
def smart_folders_view():
    if "token" not in session:
        return redirect(url_for("login"))
        
    headers = {"Authorization": f"Bearer {session['token']}"}
    folders = []
    
    return render_template("smart_folders.html", user=session.get("user"), folders=folders)


@app.route("/analytics")
def library_analytics_view():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("analytics.html", user=session.get("user"))

@app.route("/notifications")
def notifications_view():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("notifications.html", user=session.get("user"))

@app.route("/billing")
def billing_dashboard():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("billing.html", user=session.get("user"))

if __name__ == "__main__":
    app.run(port=5000, debug=True)