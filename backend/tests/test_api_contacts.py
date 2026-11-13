"""通讯录接口单测。"""
from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_profile import ContactProfile
from backend.models.conversation import Conversation


def make_contact(**over):
    fields = {"chat_type": 1}
    fields.update(over)
    conv = Conversation(openid="dev01", **fields)
    db.session.add(conv)
    db.session.commit()
    return conv


def make_roster(wxid, **over):
    """造 contact 表联系人（全量同步入库的形态）。"""
    fields = {"type": Contact.TYPE_FRIEND}
    fields.update(over)
    c = Contact(openid="dev01", wxid=wxid, **fields)
    db.session.add(c)
    db.session.commit()
    return c


def test_roster_contacts_listed(client):
    """contact 表的全量联系人进通讯录（没聊过天也在，无会话信息）。"""
    make_roster("wxid_new", name="新好友")
    make_roster("1@chatroom", type=Contact.TYPE_GROUP, name="报价群")

    friends = client.get("/api/contacts?type=friends").get_json()["data"]
    groups = client.get("/api/contacts?type=groups").get_json()["data"]

    assert [c["name"] for c in friends["list"]] == ["新好友"]
    assert friends["list"][0]["conversation_id"] is None
    assert friends["list"][0]["unread_count"] == 0
    assert [c["name"] for c in groups["list"]] == ["报价群"]


def test_roster_contact_with_conversation_links(client):
    """通讯录联系人已有会话时，挂上会话信息（未读/摘要/会话 id）。"""
    make_roster("wxid_customer")
    conv = make_contact(wxid="wxid_customer", name="张师傅", unread_count=2, last_msg="在吗")

    data = client.get("/api/contacts?type=friends").get_json()["data"]

    assert data["total"] == 1  # 同一 wxid 只出现一次（contact 为主）
    row = data["list"][0]
    assert row["conversation_id"] == conv.id
    assert row["name"] == "张师傅"  # contact 缺资料时回退显示会话里已解析的昵称
    assert row["unread_count"] == 2
    assert row["last_msg"] == "在吗"


def test_keyword_hits_remark(client):
    """keyword 命中业务备注（contact 表搜索包含备注）。"""
    make_roster("wxid_r", name="王老板")
    db.session.add(ContactProfile(wxid="wxid_r", remark="月结大客户", tags=[]))
    make_roster("wxid_other", name="李四")
    db.session.commit()

    data = client.get("/api/contacts?type=friends&keyword=月结").get_json()["data"]

    assert [c["name"] for c in data["list"]] == ["王老板"]


def test_roster_other_device_hidden(client):
    """多设备隔离：别的设备的联系人不进当前通讯录。"""
    db.session.add(Contact(openid="other02", wxid="wxid_x", type=Contact.TYPE_FRIEND, name="别家的"))
    db.session.commit()

    data = client.get("/api/contacts?type=friends").get_json()["data"]

    assert data["list"] == []


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


def test_keyword_hits_pinyin(client):
    """拼音搜索：全拼 zhangfeng / 首字母 zf 都能命中 张峰；出参带 pinyin/initials。"""
    make_contact(wxid="wxid_a", name="张峰")
    make_contact(wxid="wxid_b", name="李四")

    for kw in ("zhang", "zhangfeng", "zf"):
        data = client.get(f"/api/contacts?type=friends&keyword={kw}").get_json()["data"]
        assert [c["name"] for c in data["list"]] == ["张峰"], kw

    rows = client.get("/api/contacts?type=friends").get_json()["data"]["list"]
    row = next(c for c in rows if c["name"] == "张峰")
    assert row["pinyin"] == "zhangfeng"
    assert row["initials"] == "zf"


def test_keyword_hits_remark_pinyin(client):
    """拼音搜索命中备注：remark=张峰的客户 输入 zhang 可搜到 王老板。"""
    make_roster("wxid_r", name="王老板")
    db.session.add(ContactProfile(wxid="wxid_r", remark="张峰的客户", tags=[]))
    db.session.commit()

    data = client.get("/api/contacts?type=friends&keyword=zhang").get_json()["data"]

    assert [c["name"] for c in data["list"]] == ["王老板"]


def test_keyword_pinyin_respects_char_boundary(client):
    """拼音匹配按字边界对齐：housheng 只命中 后生仔，不再跨字命中 杭|州|圣|驰。"""
    make_contact(wxid="wxid_h", name="杭州圣驰汽配")
    make_contact(wxid="wxid_b", name="后生仔")
    make_contact(wxid="wxid_z", name="张峰")

    data = client.get("/api/contacts?type=friends&keyword=housheng").get_json()["data"]
    assert [c["name"] for c in data["list"]] == ["后生仔"]

    # heng 在 zhang 词中间 / feng 首字母串里都不该命中 张峰
    data = client.get("/api/contacts?type=friends&keyword=heng").get_json()["data"]
    assert [c["name"] for c in data["list"]] == []

    # 字边界内的中段拼音仍命中：sheng 从"圣"/"生"的拼音开头起
    data = client.get("/api/contacts?type=friends&keyword=sheng").get_json()["data"]
    assert {c["name"] for c in data["list"]} == {"杭州圣驰汽配", "后生仔"}


def test_extras_use_negative_id_and_profile_resolve(client):
    """补集（会话only）条目 id 取负：与 contact 表 id 隔离，档案按负 id 解析回会话行。"""
    make_roster("wxid_roster", name="正册联系人")     # contact 表行
    conv = make_contact(wxid="wxid_extra", name="补集联系人")  # 无 contact 行 → 补集

    items = client.get("/api/contacts?type=friends").get_json()["data"]["list"]
    by_name = {c["name"]: c for c in items}
    extra = by_name["补集联系人"]

    assert extra["id"] == -conv.id
    assert extra["conversation_id"] == conv.id

    # 负 id 反查档案：解析回会话行的 wxid（不落到同号的 contact 行上）
    data = client.get(f"/api/contacts/{-conv.id}/profile").get_json()["data"]
    assert data == {"remark": "", "tags": []}


def test_keyword_ignores_wxid(client):
    """脱敏契约：wxid 不参与搜索（前端已不可见，搜 wxid 片段不应命中）。"""
    make_contact(wxid="wxid_customer", name=None)
    make_contact(wxid="wxid_other", name="王五")

    data = client.get("/api/contacts?type=friends&keyword=customer").get_json()["data"]

    assert data["list"] == []


def test_contacts_mask_wxid(client):
    """脱敏契约：通讯录条目不含 wxid；未解析名称 → name=None + alias，头像一并匿名。"""
    named = make_roster("wxid_named", name="客户乙")
    unnamed = make_roster("wxid_anon_88")

    items = client.get("/api/contacts?type=friends").get_json()["data"]["list"]
    by_id = {c["id"]: c for c in items}
    n, u = by_id[named.id], by_id[unnamed.id]

    assert n["name"] == "客户乙"
    assert n["avatar"] is None  # 有名无图：不下发头像（前端首字兜底）
    assert "wxid" not in n
    assert n["alias"]

    assert u["name"] is None
    assert u["avatar"] is None
    assert "wxid" not in u
    assert u["alias"]


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
    """letter：中文名取拼音首字母；未解析名称归入 # 排最后。"""
    make_contact(wxid="wxid_c", name="陈国斌")      # C
    make_contact(wxid="wxid_b", name="白云")        # B
    make_contact(wxid="wxid_anon", name=None)       # 未解析 → #

    data = client.get("/api/contacts?type=friends").get_json()["data"]
    letters = [(c["letter"], c["name"]) for c in data["list"]]

    assert letters == [("B", "白云"), ("C", "陈国斌"), ("#", None)]


# ---------- 联系人档案（备注/标签，按 contact_id 访问——脱敏契约） ----------


def test_profile_default_empty(client):
    """无档案记录时返回默认空值。"""
    c = make_roster("wxid_a")

    data = client.get(f"/api/contacts/{c.id}/profile").get_json()["data"]

    assert data == {"remark": "", "tags": []}


def test_profile_put_then_get(client):
    """PUT 创建档案后 GET 可读回。"""
    c = make_roster("wxid_a")
    r = client.put(f"/api/contacts/{c.id}/profile", json={"remark": "月结客户", "tags": ["奔驰超豪", "月结"]})

    assert r.get_json()["code"] == 0
    data = client.get(f"/api/contacts/{c.id}/profile").get_json()["data"]

    assert data == {"remark": "月结客户", "tags": ["奔驰超豪", "月结"]}


def test_profile_put_updates_existing(client):
    """重复 PUT 走更新而非新建。"""
    c = make_roster("wxid_a")
    client.put(f"/api/contacts/{c.id}/profile", json={"remark": "旧备注", "tags": ["a"]})
    client.put(f"/api/contacts/{c.id}/profile", json={"remark": "新备注", "tags": ["a", "b"]})

    data = client.get(f"/api/contacts/{c.id}/profile").get_json()["data"]

    assert data["remark"] == "新备注"
    assert data["tags"] == ["a", "b"]


def test_profile_rejects_over_limits(client):
    """备注超 100 字 / 标签超 10 个 / 单标签超 12 字均拒绝。"""
    ca, cb, cc = make_roster("wxid_a"), make_roster("wxid_b"), make_roster("wxid_c")
    r1 = client.put(f"/api/contacts/{ca.id}/profile", json={"remark": "x" * 101, "tags": []})
    r2 = client.put(f"/api/contacts/{cb.id}/profile", json={"remark": "", "tags": [f"t{i}" for i in range(11)]})
    r3 = client.put(f"/api/contacts/{cc.id}/profile", json={"remark": "", "tags": ["x" * 13]})

    assert r1.get_json()["code"] == 400
    assert r2.get_json()["code"] == 400
    assert r3.get_json()["code"] == 400


def test_profile_tags_dedupe_and_trim(client):
    """标签自动去空白、去重、去空项。"""
    c = make_roster("wxid_a")
    client.put(f"/api/contacts/{c.id}/profile", json={"remark": "", "tags": [" 月结 ", "月结", "", "奔驰"]})

    data = client.get(f"/api/contacts/{c.id}/profile").get_json()["data"]

    assert data["tags"] == ["月结", "奔驰"]


def test_profile_contact_not_found(client):
    """contact_id 不存在（或跨设备）：404，档案接口不按 wxid 裸查。"""
    resp = client.get("/api/contacts/99999/profile")

    assert resp.status_code == 404
