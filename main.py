from flask import Flask
from config import Config
from database import init_db
from routes.api import api

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(api, url_prefix='/api')

    with app.app_context():
        init_db()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)