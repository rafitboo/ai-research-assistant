from flask import Flask, render_template

app = Flask(__name__)
app.secret_key = "super_secret_course_key"

@app.route("/")
def index():
    return "Flask Frontend is running. Tailwind HTML will render here."

if __name__ == "__main__":
    app.run(port=5000, debug=True)