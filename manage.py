from flask import Flask
from app import create_app
# from .app.routes import main

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
