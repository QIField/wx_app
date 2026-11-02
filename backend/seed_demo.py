"""演示数据：往当前环境数据库插入假会话与消息（仅开发调试用）。

用法：python -m backend.seed_demo
幂等：已有演示会话（openid=demo）就跳过；真实联调用的是真实 openid，互不干扰。
"""
from datetime import datetime, timedelta

from backend.app import create_app
from backend.extensions import db
from backend.models import Conversation, Message

DEMO_OPENID = "demo"
NOW = datetime.now()

# (wxid, 类型, 名称, 未读数, 是否置顶, 最后消息几分钟前, [(方向,类型,内容,几分钟前)])
DEMO = [
    ("wxid_zhang", 1, "张师傅-红旗修理厂", 2, 0, 3, [
        (1, 1, "您好，09年帕萨特 1.8T 自动变速箱，大修包有货吗？", 25),
        (2, 1, "在的，原厂件和副厂件都有，要哪种？", 22),
        (1, 1, "副厂就行，报价发一下", 5),
        (1, 1, "今天能发货吗", 3),
    ]),
    ("wxid_liji", 1, "李记自动波箱", 0, 0, 60, [
        (1, 1, "01M 阀体总成多少钱", 180),
        (2, 1, "翻新件 1850，全新原厂 4200", 120),
        (1, 1, "要翻新的，发顺丰", 65),
        (2, 1, "好，明天上午发出，单号回头发您", 60),
    ]),
    ("99988888@chatroom", 2, "华胜汽修配价一群", 5, 0, 8, [
        (1, 1, "群里哪位有 6HP21 的供应商电话", 40),
        (1, 1, "广州陈总 138-xxxx-6666", 35),
        (2, 1, "我们这也有，需要看报价单吗", 20),
        (1, 1, "要的，发我一份", 12),
        (1, 1, "急件，今天定", 8),
    ]),
    ("wxid_wang", 1, "王小二-闪电快修", 1, 0, 30, [
        (1, 1, "图片发你了，看看这个损伤程度能修吗", 35),
        (1, 2, "[图片]", 30),
    ]),
    ("77665544@chatroom", 2, "快修联盟-总部群", 0, 1, 240, [
        (1, 1, "本周配件对账单已发邮箱，请查收", 260),
        (2, 1, "收到", 240),
    ]),
    ("wxid_laochen", 1, "老陈配货", 0, 0, 1440, [
        (1, 5, "[链接] 变速箱维修行业周报（10月第4期）", 1500),
        (2, 1, "谢谢陈哥，周末细看", 1440),
    ]),
]


def _ensure_demo_user():
    """演示账号：绑定 demo 设备（幂等，绑定已存在则跳过）。"""
    from werkzeug.security import generate_password_hash

    from backend.models.user import ROLE_AGENT, User
    from backend.models.user_device import UserDevice

    if UserDevice.query.filter_by(openid=DEMO_OPENID).first() is not None:
        return
    user = User(username="demo", name="演示客服", role=ROLE_AGENT,
                password_hash=generate_password_hash("123456"))
    db.session.add(user)
    db.session.flush()
    db.session.add(UserDevice(user_id=user.id, openid=DEMO_OPENID, remark="演示设备"))
    db.session.commit()
    print("已创建演示账号 demo / 123456（绑定 demo 设备）")


def seed():
    app = create_app()
    with app.app_context():
        _ensure_demo_user()
        exists = Conversation.query.filter_by(openid=DEMO_OPENID).first()
        if exists is not None:
            print("演示数据已存在，跳过（要重造先删 wx_app_dev.db）")
            return

        conv_count = msg_count = 0
        for wxid, chat_type, name, unread, pinned, last_ago, msgs in DEMO:
            conv = Conversation(
                openid=DEMO_OPENID,
                wxid=wxid,
                chat_type=chat_type,
                name=name,
                unread_count=unread,
                pinned=pinned,
                last_msg=msgs[-1][2][:50],
                last_msg_at=NOW - timedelta(minutes=last_ago),
            )
            db.session.add(conv)
            db.session.flush()
            conv_count += 1

            for direction, msg_type, content, ago in msgs:
                payload = {}
                if msg_type == 2:
                    payload = {"img_url": "https://example.com/demo.jpg"}
                if msg_type == 5:
                    payload = {"title": "行业周报", "link_url": "https://example.com"}
                db.session.add(Message(
                    conversation_id=conv.id,
                    msg_type=msg_type,
                    direction=direction,
                    sender_wxid=wxid,
                    sender_name=name if direction == 1 else "客服",
                    content=content,
                    payload=payload,
                    middle_msg_id=f"demo-{conv.id}-{ago}",
                    create_time=NOW - timedelta(minutes=ago),
                    status=Message.ST_SENT,
                ))
                msg_count += 1

        db.session.commit()
        print(f"完成：{conv_count} 个会话、{msg_count} 条消息")


if __name__ == "__main__":
    seed()
