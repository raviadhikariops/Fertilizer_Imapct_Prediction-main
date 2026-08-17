import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("FLASK_APP", "app.py")
    os.environ.setdefault("PYTHONPATH", os.getcwd())
    from app import app

    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)
