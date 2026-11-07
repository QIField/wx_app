"""全量名册对齐全流程：通讯录与群成员共用同一套规则。

两类同步完全同构，抽出来避免“两套实现慢慢跑偏”：
- 名册里新出现的 key：交给调用方创建（各表字段不同）
- 旧行仍在名册：曾被删除则复活（保留原 id，不产生重复行）
- 旧行不在名册：标记删除（可恢复）

调用方必须先确认名册非空——中间方偶发返回空数组时，
不能把整份名册误判为“全部消失”。
"""


def reconcile(existing, incoming_keys):
    """按名册对齐一批本地行。

    existing: {key: row}，必须包含已删除行（否则复活逻辑失效）
    incoming_keys: 名册全量 key 列表
    返回 (需新建的 key 列表, 是否有变更)
    """
    created = []
    incoming = set(incoming_keys)
    changed = False
    for key in incoming_keys:
        row = existing.get(key)
        if row is None:
            created.append(key)
        elif row.is_deleted:  # 重新出现：复活旧行
            row.restore()
            changed = True
    for key, row in existing.items():
        if key not in incoming and not row.is_deleted:  # 名册里没有 = 已消失
            row.soft_delete()
            changed = True
    return created, changed
