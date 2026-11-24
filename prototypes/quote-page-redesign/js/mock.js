/**
 * mock.js — 报价页面模拟数据（单一数据源）
 * 未来替换为真实 API 调用，保持数据结构不变
 */

/** 离线占位图：SVG data URL，白底 + 品牌色圆形 + 配件缩写 */
function generatePartImg(label, color) {
  const abbr = (label || '').slice(0, 2)
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'>
    <defs><radialGradient id='g' cx='50%' cy='40%' r='60%'>
      <stop offset='0%' stop-color='${color}' stop-opacity='0.25'/>
      <stop offset='100%' stop-color='${color}' stop-opacity='0.04'/>
    </radialGradient></defs>
    <rect width='64' height='64' fill='#FAFBFD' rx='6'/>
    <circle cx='32' cy='28' r='18' fill='url(#g)'/>
    <circle cx='32' cy='28' r='10' fill='${color}' opacity='0.18'/>
    <circle cx='32' cy='28' r='6' fill='${color}' opacity='0.4'/>
    <text x='32' y='54' text-anchor='middle' font-size='10' font-family='PingFang SC, sans-serif' fill='${color}' font-weight='600'>${abbr}</text>
  </svg>`
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
}

export const DB = {
  // 车辆信息
  vehicle: {
    engineModel: '256 900',
    fuelType: '汽油型 V223',
    chassisModel: '221',
    transmission: '手自一体变速箱(AT)',
    yearPattern: '2021款',
    vin: 'WIKG65K02MA854389',
    brand: '奔驰',
    model: 'S级',
    displacement: '3.0T'
  },

  // 客户信息
  customer: {
    name: '博瑞中国车安体验群',
    type: '智驾引擎',
    inquiryNo: 'XJ104159',
    quoteNo: 'BJ20261124-001',
    quotePrice: '¥ 258.00',
    createdAt: '2026-11-19 10:03:33',
    inquiryPerson: '张悦',
    wechatId: 'bw_zhangyue'
  },

  // 询价配件列表
  parts: [
    {
      id: 1,
      name: '火花塞',
      oe: 'A2541590000',
      brand: '科帝/CORT',
      brandType: 'ECO',
      quantity: 4,
      stock: 28,
      unitPrice: 68.00
    },
    {
      id: 2,
      name: '机油滤清器',
      oe: 'A2751840025',
      brand: '曼牌/MANN',
      brandType: 'OEM',
      quantity: 1,
      stock: 52,
      unitPrice: 45.00
    },
    {
      id: 3,
      name: '空气滤清器',
      oe: 'A2740940004',
      brand: '马勒/MAHLE',
      brandType: 'OEM',
      quantity: 1,
      stock: 18,
      unitPrice: 88.00
    },
    {
      id: 4,
      name: '刹车片（前）',
      oe: 'A0074205520',
      brand: '布雷博/Brembo',
      brandType: 'AMG',
      quantity: 2,
      stock: 6,
      unitPrice: 358.00
    }
  ],

  // 报价明细（可编辑表格行）
  quoteItems: [
    {
      id: 1,
      image: generatePartImg('火花塞', '#E82016'),
      oe: 'A2541590000',
      customCode: 'A2541590000',
      brand: '科帝/CORT',
      brandColor: 'red',
      spec: '适配 A254 M254',
      salePrice: 85.00,
      costPrice: 68.00,
      tax: 13.00,
      stock: 28,
      warranty: '1年/2万km',
      remark: '原厂配套'
    },
    {
      id: 2,
      image: generatePartImg('火花塞', '#1A2F5C'),
      oe: 'A2541590000',
      customCode: 'A2541590001',
      brand: 'LBN(力邦)',
      brandColor: '',
      spec: '通用款',
      salePrice: 58.00,
      costPrice: 42.00,
      tax: 9.00,
      stock: 150,
      warranty: '半年/1万km',
      remark: ''
    },
    {
      id: 3,
      image: generatePartImg('机油滤', '#2F6FF0'),
      oe: 'A2751840025',
      customCode: 'A2751840000',
      brand: '曼牌/MANN',
      brandColor: 'red',
      spec: 'HU711XZ',
      salePrice: 58.00,
      costPrice: 45.00,
      tax: 8.00,
      stock: 52,
      warranty: '1年',
      remark: '长寿命款'
    },
    {
      id: 4,
      image: generatePartImg('空气滤', '#15803D'),
      oe: 'A2740940004',
      customCode: 'A2740940000',
      brand: '马勒/MAHLE',
      brandColor: 'red',
      spec: 'LX3494',
      salePrice: 108.00,
      costPrice: 88.00,
      tax: 13.50,
      stock: 18,
      warranty: '1年',
      remark: ''
    },
    {
      id: 5,
      image: generatePartImg('刹车片', '#B45309'),
      oe: 'A0074205520',
      customCode: 'A0074205520',
      brand: '布雷博/Brembo',
      brandColor: 'red',
      spec: 'P85020',
      salePrice: 398.00,
      costPrice: 358.00,
      tax: 51.74,
      stock: 6,
      warranty: '1年/3万km',
      remark: '高性能陶瓷'
    }
  ],

  // 费用汇总
  summary: {
    subtotal: 707.00,        // 小计
    taxTotal: 95.24,          // 税费合计
    discount: 50.00,          // 优惠金额
    finalPrice: 752.24,       // 最终报价
    expiryDate: '2026-12-04', // 有效期
    itemCount: 5,
    validDays: 10
  },

  // 常用 OE 码历史
  recentOeCodes: [
    'A2541590000', 'A2751840025', 'A2740940004', 'A0074205520',
    'A2050014300', 'A2128300318', 'A0001401500'
  ]
};
