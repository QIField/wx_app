"""共享扩展实例：各模块从这里导入，避免循环导入。"""
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock

db = SQLAlchemy()
sock = Sock()
