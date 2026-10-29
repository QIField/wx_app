"""发消息类接口封装：只拼参数和调 client，不碰数据库。

对应中间方 send_api。先 post_xxx 下发，再用同一个 uuid 调
get_result（自动加 get_ 前缀）查询发送结果。
"""
from backend.adapter import client


def post_text(to_wxid, content, ats="", uuid=None):
    """发文本。ats=群内要@的人，wxid 逗号分隔。"""
    return client.call(
        "post_text_message",
        {"to_wxid": to_wxid, "content": content, "ats": ats},
        uuid=uuid,
    )


def post_image(to_wxid, img_url, uuid=None):
    """发图片。"""
    return client.call(
        "post_image_message",
        {"to_wxid": to_wxid, "img_url": img_url},
        uuid=uuid,
    )


def post_file(to_wxid, file_url, file_name, uuid=None):
    """发文件。"""
    return client.call(
        "post_file_message",
        {"to_wxid": to_wxid, "file_url": file_url, "file_name": file_name},
        uuid=uuid,
    )


def post_video(to_wxid, video_url, thumb_url="", video_duration=0, uuid=None):
    """发视频。"""
    return client.call(
        "post_video_message",
        {
            "to_wxid": to_wxid,
            "video_url": video_url,
            "thumb_url": thumb_url,
            "video_duration": video_duration,
        },
        uuid=uuid,
    )


def post_link(to_wxid, title, desc, link_url, thumb_url="", uuid=None):
    """发链接卡片（报价处理台发报价也走这里）。"""
    return client.call(
        "post_link_message",
        {
            "to_wxid": to_wxid,
            "title": title,
            "desc": desc,
            "link_url": link_url,
            "thumb_url": thumb_url,
        },
        uuid=uuid,
    )


def get_result(action, uuid):
    """查下发结果：action 传 post_xxx，自动加 get_ 前缀。"""
    return client.call("get_" + action, {}, uuid=uuid)
