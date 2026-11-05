"""共享扩展实例：各模块从这里导入，避免循环导入。"""
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock

# 数据库在公网（测试库），TCP 长连接会被 NAT/防火墙在空闲期静默掐断：
# - pool_pre_ping：每次取连接前先探活，死连接自动重建（否则复用死连接直接 500）
# - pool_recycle：280s 主动回收，避开常见的 300s 空闲掐断窗口
db = SQLAlchemy(engine_options={
    "pool_pre_ping": True,
    "pool_recycle": 280,
})
sock = Sock()
