"""通讯录接口单测。"""
from backend.extensions import db
from backend.models.conversation import Conversation


def make_contact(**over):
    fields = {"chat_type": 1}
    fields.update(over)
    conv = Conversation(openid="dev01", **fields)
    db.session.add(conv)
    db.session.commit()
    return conv


def test_friends_only_single_chat(client):
    """type=friends 只返回单聊会话。"""
    make_contact(wxid="wxid_a", name="阿明")
    make_contact(wxid="wxid_g", name="报价群", chat_type=2)

    data = client.get("/api/contacts?type=friends").get_json()["data"]

    assert [c["name"] for c in data["list"]] == ["阿明"]
    assert data["total"] == 1


def test_groups_only_group_chat(client):
    """type=groups 只返回群聊会话。"""
    make_contact(wxid="wxid_a", name="阿明")
    make_contact(wxid="wxid_g", name="报价群", chat_type=2)

    data = client.get("/api/contacts?type=groups").get_json()["data"]

    assert [c["name"] for c in data["list"]] == ["报价群"]


def test_keyword_hits_name(client):
    """keyword 命中 name。"""
    make_contact(wxid="wxid_a", name="张师傅")
    make_contact(wxid="wxid_b", name="李四")

    data = client.get("/api/contacts?type=friends&keyword=张").get_json()["data"]

    assert [c["name"] for c in data["list"]] == ["张师傅"]


def test_keyword_hits_wxid(client):
    """keyword 命中 wxid（资料未解析也能搜到）。"""
    make_contact(wxid="wxid_customer", name=None)
    make_contact(wxid="wxid_other", name="王五")

    data = client.get("/api/contacts?type=friends&keyword=customer").get_json()["data"]

    assert [c["wxid"] for c in data["list"]] == ["wxid_customer"]


def test_keyword_no_match(client):
    """keyword 无命中返回空列表。"""
    make_contact(wxid="wxid_a", name="阿明")

    data = client.get("/api/contacts?type=friends&keyword=不存在").get_json()["data"]

    assert data["list"] == []
    assert data["total"] == 0


def test_excludes_deleted(client):
    """软删除的会话不进通讯录。"""
    conv = make_contact(wxid="wxid_dead", name="已删除")
    conv.deleted_at = db.func.now()
    db.session.commit()

    data = client.get("/api/contacts?type=friends").get_json()["data"]

    assert data["list"] == []


def test_invalid_type_rejected(client):
    """非法 type 返回业务错误 400。"""
    resp = client.get("/api/contacts?type=whatever")

    assert resp.status_code == 400
    assert resp.get_json()["code"] == 400


def test_letter_pinyin_and_fallback(client):
    """letter：中文名取拼音首字母；数字开头归入 # 排最后。"""
    make_contact(wxid="wxid_c", name="陈国斌")   # C
    make_contact(wxid="wxid_b", name="白云")     # B
    make_contact(wxid="139****9515", name=None)  # 数字开头 → #

    data = client.get("/api/contacts?type=friends").get_json()["data"]
    letters = [(c["letter"], c["name"]) for c in data["list"]]

    assert letters == [("B", "白云"), ("C", "陈国斌"), ("#", "139****9515")]


# ---------- 联系人档案（备注/标签） ----------


def test_profile_default_empty(client):
    """无档案记录时返回默认空值。"""
    data = client.get("/api/contacts/wxid_a/profile").get_json()["data"]

    assert data == {"remark": "", "tags": []}


def test_profile_put_then_get(client):
    """PUT 创建档案后 GET 可读回。"""
    r = client.put("/api/contacts/wxid_a/profile", json={"remark": "月结客户", "tags": ["奔驰超豪", "月结"]})

    assert r.get_json()["code"] == 0
    data = client.get("/api/contacts/wxid_a/profile").get_json()["data"]

    assert data == {"remark": "月结客户", "tags": ["奔驰超豪", "月结"]}


def test_profile_put_updates_existing(client):
    """重复 PUT 走更新而非新建。"""
    client.put("/api/contacts/wxid_a/profile", json={"remark": "旧备注", "tags": ["a"]})
    client.put("/api/contacts/wxid_a/profile", json={"remark": "新备注", "tags": ["a", "b"]})

    data = client.get("/api/contacts/wxid_a/profile").get_json()["data"]

    assert data["remark"] == "新备注"
    assert data["tags"] == ["a", "b"]


def test_profile_rejects_over_limits(client):
    """备注超 100 字 / 标签超 10 个 / 单标签超 12 字均拒绝。"""
    r1 = client.put("/api/contacts/wxid_a/profile", json={"remark": "x" * 101, "tags": []})
    r2 = client.put("/api/contacts/wxid_b/profile", json={"remark": "", "tags": [f"t{i}" for i in range(11)]})
    r3 = client.put("/api/contacts/wxid_c/profile", json={"remark": "", "tags": ["x" * 13]})

    assert r1.get_json()["code"] == 400
    assert r2.get_json()["code"] == 400
    assert r3.get_json()["code"] == 400


def test_profile_tags_dedupe_and_trim(client):
    """标签自动去空白、去重、去空项。"""
    client.put("/api/contacts/wxid_a/profile", json={"remark": "", "tags": [" 月结 ", "月结", "", "奔驰"]})

    data = client.get("/api/contacts/wxid_a/profile").get_json()["data"]

    assert data["tags"] == ["月结", "奔驰"]
