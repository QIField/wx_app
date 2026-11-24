"""quote_inquiry 询价表模型（自动报价流水线的主数据表）。

状态机（契约 B，docs/auto-quote-plan.md）：
  pending  待报价：quoted=false 且字段完整，等待报价计算与自动发送
  review   待人工：quoted=true（跟进旧报价）或字段缺失，进右栏预览等人工
  blocked  拦截：配件命中黑名单
  sent     已报价：报价已自动发送（阶段 5 回写）
  ignored  忽略：人工标记不需要处理
一条询价对应 AI 提取出的一个场景（同一批分析可产出多条）。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class QuoteInquiry(db.Model, SoftDeleteMixin):
    __tablename__ = "quote_inquiry"

    ST_PENDING = 0
    ST_REVIEW = 1
    ST_BLOCKED = 2
    ST_SENT = 3
    ST_IGNORED = 4
    STATUS_LABELS = {
        ST_PENDING: "待报价", ST_REVIEW: "待人工", ST_BLOCKED: "拦截",
        ST_SENT: "已报价", ST_IGNORED: "忽略",
    }

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.BigInteger, nullable=False, comment="触发分析的会话")
    message_id = db.Column(db.BigInteger, comment="触发该询价的原始消息 ID（用于前端定位聊天气泡）")
    sender_name = db.Column(db.String(128), comment="询价人（AI 场景提取）")
    vin = db.Column(db.String(64), comment="提取的 VIN，缺字段场景为空")
    part_name = db.Column(db.String(64), comment="配件名称")
    oem_no = db.Column(db.Text, comment="AI 提取的 OE（逗号分隔多件，VARCHAR(64) 不够用）")
    quoted = db.Column(
        db.Boolean, nullable=False, default=False,
        comment="AI 判断是否跟进旧报价（true=二次议价，不自动发）",
    )
    inquiry_time = db.Column(db.String(32), comment="AI 场景的询价时间原文（对账用）")
    inquiry_content = db.Column(db.Text, comment="询价原文摘要")
    status = db.Column(
        db.SmallInteger, nullable=False, default=ST_PENDING,
        comment="0待报价 1待人工 2拦截 3已报价 4忽略",
    )
    price_json = db.Column(db.JSON, comment="报价结果（阶段 4 写；含改价后价格）")
    override_pricing = db.Column(
        db.JSON, comment="人工改价覆盖（detail 页行内改价保存；结构 {items:[{oe,final_price}]}）",
    )
    sent_at = db.Column(db.DateTime, comment="自动发送时间（阶段 5 回写）")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.Index("idx_inquiry_conv", "conversation_id", "status"),
        db.Index("idx_inquiry_msg", "message_id"),
    )
