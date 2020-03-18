# coding: utf8
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
# import pymysql
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:1224@127.0.0.1:3306/movies'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = 'b917cacccbd14d759fb93422c719a669'
app.config['UP_DIR'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads/')
app.debug = True
db = SQLAlchemy(app)

# 配置redis
from flask_redis import FlaskRedis
app.config["REDIS_URL"] = 'redis://:{password}@{host}:{port}/1'.format(
    host='127.0.0.1',
    port=6379,
    password='',
)
rd = FlaskRedis(app)


from app.home import home as home_blueprint
from app.admin import admin as admin_blueprint

app.register_blueprint(home_blueprint)
app.register_blueprint(admin_blueprint, url_prefix='/admin')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('home/404.html'), 404