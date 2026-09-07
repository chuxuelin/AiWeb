import flask

app = flask.Flask(__name__, template_folder="templates")
app.secret_key = "health-demo-secret"

TEST_EMAIL = "admin"
TEST_PASSWORD = "123"


@app.route("/")
def index():
    if flask.session.get("logged_in"):
        return flask.redirect(flask.url_for("dashboard"))
    return flask.render_template("base.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if flask.request.method == "POST":
        email = flask.request.form.get("email", "")
        password = flask.request.form.get("password", "")

        if email == TEST_EMAIL and password == TEST_PASSWORD:
            flask.session["logged_in"] = True
            flask.session["email"] = email
            return flask.redirect(flask.url_for("dashboard"))

        return flask.render_template("base.html", error="邮箱或密码错误，请使用测试账号：admin / 123")

    if flask.session.get("logged_in"):
        return flask.redirect(flask.url_for("dashboard"))
    return flask.render_template("base.html")


@app.route("/dashboard")
def dashboard():
    if not flask.session.get("logged_in"):
        return flask.redirect(flask.url_for("login"))
    return flask.render_template("model.html")


@app.route("/logout")
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
