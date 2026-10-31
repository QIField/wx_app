"""发消息类接口封装：只拼参数和调 client，不碰数据库。

对应中间方 send_api。先 post_xxx 下发，再用同一个 uuid 调
get_result（自动加 get_ 前缀）查询发送结果。
openid 是设备标识，多设备后由发送编排层按会话所属设备传入。
"""
from backend.adapter import client


def post_text(to_wxid, content, ats="", uuid=None, openid=""):
    """发文本。ats=群内要@的人，wxid 逗号分隔。"""
    return client.call(
        "send_api",
        "post_text_message",
        {"to_wxid": to_wxid, "content": content, "ats": ats},
        uuid=uuid,
        openid=openid,
    )


def post_image(to_wxid, img_url, uuid=None, openid=""):
    """发图片。"""
    return client.call(
        "send_api",
        "post_image_message",
        {"to_wxid": to_wxid, "img_url": img_url},
        uuid=uuid,
        openid=openid,
    )


def post_file(to_wxid, file_url, file_name, uuid=None, openid=""):
    """发文件。"""
    return client.call(
        "send_api",
        "post_file_message",
        {"to_wxid": to_wxid, "file_url": file_url, "file_name": file_name},
        uuid=uuid,
        openid=openid,
    )


def post_video(to_wxid, video_url, thumb_url="", video_duration=0, uuid=None, openid=""):
    """发视频。"""
    return client.call(
        "send_api",
        "post_video_message",
        {
            "to_wxid": to_wxid,
            "video_url": video_url,
            "thumb_url": thumb_url,
            "video_duration": video_duration,
        },
        uuid=uuid,
        openid=openid,
    )


def post_link(to_wxid, title, desc, link_url, thumb_url="", uuid=None, openid=""):
    """发链接卡片（报价处理台发报价也走这里）。"""
    return client.call(
        "send_api",
        "post_link_message",
        {
            "to_wxid": to_wxid,
            "title": title,
            "desc": desc,
            "link_url": link_url,
            "thumb_url": thumb_url,
        },
        uuid=uuid,
        openid=openid,
    )


def revoke(to_wxid, msg_id, new_msg_id, create_time, uuid=None, openid=""):
    """撤回消息（实测：文字消息发送结果 msgId=0，传 "0" 靠 new_msg_id 定位）。

    create_time 为发出时刻的 unix 秒字符串；结果查 get_revoke_message。
    """
    return client.call(
        "send_api",
        "revoke_message",
        {"to_wxid": to_wxid, "msg_id": msg_id, "new_msg_id": new_msg_id, "create_time": create_time},
        uuid=uuid,
        openid=openid,
    )


def get_result(action, uuid, openid=""):
    """查下发结果：action 传 post_xxx，自动加 get_ 前缀。"""
    return client.call("send_api", "get_" + action, {}, uuid=uuid, openid=openid)
