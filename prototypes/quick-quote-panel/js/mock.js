/* ===== 快捷报价 · Mock 数据层 =====
   全部响应结构与 docs/quick-quote-api-test.md 实测记录同构（字段名/类型逐一对齐）。
   仅造数，不调真实模型/服务。 */

(function () {
  const IMG_PRODUCT = 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=auto%20parts%20product%20photo%2C%20black%20rubber%20radiator%20coolant%20water%20hose%20pipe%20for%20Mercedes%20Benz%20car%2C%20clean%20white%20studio%20background%2C%20e-commerce%20style%2C%20high%20detail&image_size=square';
  const IMG_THERMO = 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=automotive%20engine%20thermostat%20valve%20car%20part%2C%20metal%20circular%20thermostat%20housing%2C%20white%20studio%20background%2C%20e-commerce%20product%20photo%2C%20high%20detail&image_size=square';
  const IMG_VIN = 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=close-up%20photo%20of%20car%20VIN%20vehicle%20identification%20number%20data%20plate%20sticker%2C%20silver%20metal%20plate%20with%20engraved%20code%20WBAWX3100G0L69597%2C%20on%20car%20door%20frame%2C%20realistic%20photo&image_size=portrait_4_3';

  const ok = data => Promise.resolve({ code: 0, msg: 'success', data });

  const PRODUCT_LIST = {
    total: 1, per_page: '10', current_page: 1,
    data: {
      list: [{
        product_id: 91327,
        store_number: 'A1665000075',
        partent_number: '724500401',
        display_number: { key: 'OE', value: '1665000075' },
        product_name: '上水管（发动机冷却液软管）',
        brand_id: 1,
        cost_price: '69.00',
        store_price: '628.14',
        auto_quote: ['1280', '91327', '32464'],
        image: IMG_PRODUCT,
        sell_point: '菲尔(FREY)原厂品质 · 奔驰 M276/M166 专用 · 耐高温EPDM材质',
        child: [
          { brand_name: '菲尔(FREY)', brand_id: 1, cost_price: '69.00', store_price: '628.14', stock: 23 },
          { brand_name: '原厂', brand_id: 79, cost_price: '260.00', store_price: '628.14', stock: 6 },
          { brand_name: '盖茨(GATES)', brand_id: 43, cost_price: '109.00', store_price: '628.14', stock: 0 },
        ],
      }],
      no_exist_oe: [],
    },
  };

  const VININFO = [{
    vin: 'WBAWX3100G0L69597',
    carBrandCode: 'BMW',
    carBrandName: '宝马',
    countryCode: '中国',
    brandName: '华晨宝马',
    model: '宝马X3 20iX',
    yearPattern: '2016',
    displacement: '2.0T',
    gear: '自动挡',
    fuel: '汽油',
  }];

  const PARTNO = {
    vin: 'WBAWX3100G0L69597',
    partsNo: '节温器',
    oeCode: '11 53 8 635 689',
    oeCodeTrim: '11538635689',
    oeName: '节温器',
    stdName: '节温器总成',
    brandCode: 'BMW',
    price4s: '1270.0',
  };

  const PART_IMAGES = [{
    vin: 'WBAWX3100G0L69597',
    oeCode: '11538635689',
    partNumber: '11538635689',
    imageId: '10097483',
    position: '2',
    modal: 'X3 20iX',
    count: '1',
    extraCode: '',
    lableTop: '229', lableBottom: '251', lableLeft: '151', lableRight: '162',
    x_img_url: '/static/imgfile/1794886767_demo.png',
  }];

  const PART_IMAGES_LIST = {
    vin: 'WBAWX3100G0L69597',
    oeCode: '11538635689',
    carBrandId: 'BMW',
    imageId: '10097483',
    data: [
      { imageLabel: '1', images_position: '1', oeCode: '11 51 5 A81 BE9', oeCodeTrim: '1151 5A81BE9', oeName: '冷却液泵', stdName: '电子水泵', price4s: '5220.00', count: '1', images_lableTop: '120', images_lableBottom: '146', images_lableLeft: '205', images_lableRight: '218', extraList: [{ key: '补充说明', value: '200W-2013-04-01' }, { key: '备注', value: '' }], x_img_url: '/static/imgfile/1794886767_demo.png' },
      { imageLabel: '2', images_position: '2', oeCode: '11 53 8 635 689', oeCodeTrim: '11538635689', oeName: '节温器', stdName: '节温器总成', price4s: '1270.00', count: '1', images_lableTop: '229', images_lableBottom: '251', images_lableLeft: '151', images_lableRight: '162', extraList: [{ key: '补充说明', value: '' }, { key: '备注', value: '' }], x_img_url: '/static/imgfile/1794886767_demo.png' },
      { imageLabel: '3', images_position: '3', oeCode: '11 51 7 602 125', oeCodeTrim: '11517602125', oeName: '螺栓', stdName: '六角螺栓', price4s: '18.00', count: '3', images_lableTop: '301', images_lableBottom: '318', images_lableLeft: '188', images_lableRight: '196', extraList: [{ key: '备注', value: 'M8x34' }], x_img_url: '/static/imgfile/1794886767_demo.png' },
      { imageLabel: '4', images_position: '4', oeCode: '07 12 9 905 003', oeCodeTrim: '07129905003', oeName: 'ISA 螺栓', stdName: '组合螺栓', price4s: '30.00', count: '4', images_lableTop: '380', images_lableBottom: '396', images_lableLeft: '240', images_lableRight: '248', extraList: [{ key: '备注', value: 'M6X25' }], x_img_url: '/static/imgfile/1794886767_demo.png' },
    ],
  };

  const EXTRACT_PARTS = [
    {
      sender_name: '黄晓明', vin: 'WBAWX3100G0L69597', quoted: false,
      part_name: '油底壳\n节温器', oem_no: null,
      inquiry_time: '2026-11-17 10:20:12',
      inquiry_content: '油底壳 节温器',
      is_replied: false, first_reply_time: null, reply_content: null,
    },
    {
      sender_name: '马斯克', vin: null, quoted: true,
      part_name: '火花塞', oem_no: '885625662',
      inquiry_time: '2026-11-17 10:15:12',
      inquiry_content: '885625662火花塞多少钱',
      is_replied: true, first_reply_time: '2026-11-17 10:16:45',
      reply_content: '1、885625662 马勒 120',
    },
  ];

  const JQR = {
    jy_data: [
      { _score: 10060100.0, brand_name: '马勒', brand_initial: 'ML', custom_brand_name: '马勒(MAHLE)', en_brand_name: 'MAHLE', en_quality_name: 'MAHLE', brand_images_url: '', circle_name: null, circle_prod_id: null, city_name: '杭州', country_code: 'CN', credit_score: 98, default_code: 'PRD025071', description: '节温器总成 适配宝马N20/N46', enquiry_count: 326, level_code: 'L001', level_flag: 'A', datelastupdate: '2026-11-16 18:22:31', make: [{ id: 101, images: '', name: '宝马X3 20iX' }, { id: 102, images: '', name: '宝马525Li' }] },
      { _score: 9860500.0, brand_name: '依纳', brand_initial: 'YN', custom_brand_name: '依纳(INA)', en_brand_name: 'INA', en_quality_name: 'INA', brand_images_url: '', circle_name: null, circle_prod_id: null, city_name: '上海', country_code: 'CN', credit_score: 95, default_code: 'PRD033102', description: '节温器 原厂配套', enquiry_count: 188, level_code: 'L002', level_flag: 'B', datelastupdate: '2026-11-15 09:10:07', make: [{ id: 101, images: '', name: '宝马X3 20iX' }] },
      { _score: 9102200.0, brand_name: '盖茨', brand_initial: 'GTS', custom_brand_name: '盖茨(GATES)', en_brand_name: 'GATES', en_quality_name: 'GATES', brand_images_url: '', circle_name: null, circle_prod_id: null, city_name: '广州', country_code: 'CN', credit_score: 92, default_code: 'PRD041877', description: '节温器（含垫片）', enquiry_count: 97, level_code: 'L002', level_flag: 'B', datelastupdate: '2026-11-14 21:45:52', make: [{ id: 101, images: '', name: '宝马X3 20iX' }, { id: 103, images: '', name: '宝马320i' }] },
    ],
    xj_data: [],
  };

  const ZPY = [
    { '配件编号': '11538635689', '配件名称': '节温器', '品牌': '宝马', '物料组': '115040', '城市': '北京', '库存': 131, '折扣': 0.81, '4S含税售价': '1270.00', '4S含税进价': '800.10', '含税售价': 648.08, '发货说明': '服务站下订后3~4个工作日内发货' },
    { '配件编号': '11538635689', '配件名称': '节温器', '品牌': '宝马', '物料组': '115040', '城市': '杭州', '库存': 46, '折扣': 0.83, '4S含税售价': '1270.00', '4S含税进价': '800.10', '含税售价': 664.55, '发货说明': '服务站下订后3~4个工作日内发货' },
    { '配件编号': '11538635689', '配件名称': '节温器', '品牌': '宝马', '物料组': '115040', '城市': '武汉', '库存': 8, '折扣': 0.85, '4S含税售价': '1270.00', '4S含税进价': '800.10', '含税售价': 680.20, '发货说明': '服务站下订后2个工作日内发货' },
  ];

  const PURCHASE_HISTORY = {
    status: 200, msg: '返回成功',
    data: {
      total: { purchase_quantity: '129', totalprice: '17415.54' },
      list: {
        current_page: '1', per_page: '10', total: 81, last_page: 9,
        data: [
          { order_no: 'CGRK002202610150116', number: '1665000075', search_number: '1665000075', frey_no: '724500401', l_name_zh_default: '上水管', l_model_zh: '276/166', brand: '原厂', fullname: '广东菲尔', company_name: '佛山市巴博瑞汽车零配件有限公司', name: '李禹函', price: '260.00', amount_money: '780.00', purchase_quantity: '3', received_quantity: '3', unit: '个', warehouse: '主仓', payment_method: '月结', payment_description: '月结30天', create_date: '1792060695', expected_delivery_date: '1792147095', delivery_date: '1792100000', is_tax: '2', exchange_rate: '1.0000', status: '1' },
          { order_no: 'CGRK002202608160060', number: '1665000075', search_number: '1665000075', frey_no: '724500401', l_name_zh_default: '上水管', l_model_zh: '276/166', brand: '菲尔', fullname: '广东菲尔', company_name: '佛山市巴博瑞汽车零配件有限公司', name: '黄锐洪', price: '69.00', amount_money: '207.00', purchase_quantity: '3', received_quantity: '3', unit: '个', warehouse: '主仓', payment_method: '月结', payment_description: '月结30天', create_date: '1786873575', expected_delivery_date: '1786959975', delivery_date: '1786910000', is_tax: '2', exchange_rate: '1.0000', status: '1' },
          { order_no: 'CGRK002202607210043', number: '11538635689', search_number: '11538635689', frey_no: '724500401', l_name_zh_default: '节温器', l_model_zh: 'N20', brand: '马勒', fullname: '广州腾熙', company_name: '广州腾熙(昌盛)汽配', name: '李禹函', price: '88.00', amount_money: '440.00', purchase_quantity: '5', received_quantity: '5', unit: '个', warehouse: '主仓', payment_method: '现结', payment_description: '现结', create_date: '1784000000', expected_delivery_date: '1784086400', delivery_date: '1784040000', is_tax: '2', exchange_rate: '1.0000', status: '1' },
        ],
      },
    },
  };

  /* 场景驱动：自动报价监控流的消息 → 识别类型 → 结果 */
  const SCENARIOS = [
    {
      type: 'oe', label: 'OE',
      chat: { who: '马斯克', text: '885625662 火花塞 有货吗' },
      steps: ['识别', '查询CRM', '格式化输出'],
      product: {
        product_id: 91327, store_number: 'A885625662', partent_number: '724501102',
        display_number: { key: 'OE', value: '885625662' },
        product_name: '火花塞（铱金 4支装）', brand_id: 1,
        cost_price: '120.00', store_price: '358.00', auto_quote: ['1280', '91327', '32464'],
        image: IMG_THERMO, sell_point: '马勒(MAHLE)铱金 · 适配N20/B48 · 10万公里长效',
        child: [
          { brand_name: '马勒(MAHLE)', brand_id: 1, cost_price: '120.00', store_price: '358.00', stock: 58 },
          { brand_name: '原厂', brand_id: 79, cost_price: '210.00', store_price: '358.00', stock: 15 },
          { brand_name: 'NGK', brand_id: 43, cost_price: '136.00', store_price: '358.00', stock: 32 },
        ],
      },
      car: null,
    },
    {
      type: 'vin_img', label: 'VIN图片',
      chat: { who: '老王', img: IMG_VIN, text: '' },
      sysNote: '上一条是【老王】发的图片',
      steps: ['OCR识别', 'VIN解析', '格式化输出'],
      vininfo: VININFO[0],
      product: null,
      car: null,
    },
    {
      type: 'vin_name', label: 'VIN+名称',
      chat: { who: '黄晓明', text: 'WBAWX3100G0L69597 节温器多少钱' },
      steps: ['VIN解析', '译码', '查询CRM', '格式化输出'],
      vininfo: VININFO[0],
      partno: PARTNO,
      partImages: PART_IMAGES,
      partImagesList: PART_IMAGES_LIST,
      product: {
        product_id: 91328, store_number: 'A11538635689', partent_number: '724500877',
        display_number: { key: 'OE', value: '11538635689' },
        product_name: '节温器总成', brand_id: 1,
        cost_price: '88.00', store_price: '1270.00', auto_quote: ['1280', '91327', '32464'],
        image: IMG_THERMO, sell_point: '马勒(MAHLE) · 适配N20发动机 · 含密封垫',
        child: [
          { brand_name: '马勒(MAHLE)', brand_id: 1, cost_price: '88.00', store_price: '1270.00', stock: 46 },
          { brand_name: '原厂', brand_id: 79, cost_price: '410.00', store_price: '1270.00', stock: 3 },
          { brand_name: '盖茨(GATES)', brand_id: 43, cost_price: '105.00', store_price: '1270.00', stock: 0 },
        ],
      },
      car: VININFO[0],
    },
    {
      type: 'vin_then_name', label: 'VIN+后续名称',
      chat: { who: '黄晓明', text: '节温器 报个价' },
      contextVin: VININFO[0],
      steps: ['上下文关联', '译码', '查询CRM', '格式化输出'],
      vininfo: VININFO[0],
      partno: PARTNO,
      partImages: PART_IMAGES,
      partImagesList: PART_IMAGES_LIST,
      product: null, // 与 vin_name 场景共用结果（演示流里直接引用）
      car: VININFO[0],
    },
    {
      type: 'nl', label: '自然语言', ai: true,
      chat: { who: '泉州鑫铃', text: '老板，X3那个漏水的水管配件给我来一个，要原厂品质' },
      steps: ['AI理解', '译码', '查询CRM', '格式化输出'],
      vininfo: VININFO[0],
      partno: { ...PARTNO, oeCode: 'A 166 500 00 75', oeCodeTrim: '1665000075', oeName: '上水管', price4s: '628.14' },
      product: PRODUCT_LIST.data.list[0],
      car: VININFO[0],
      aiNote: '语义解析：X3漏水水管 → 发动机冷却液软管；"原厂品质"→ 推荐菲尔(FREY)原厂品质线',
    },
    {
      type: 'blocked', label: '黑名单',
      chat: { who: '佛山鑫铃', text: '前保险杠总成给我报个价' },
      steps: ['识别'],
      blocked: { reason: '配件黑名单', who: '保险杠总成' },
      product: null, car: null,
    },
    {
      type: 'send_fail', label: '发送失败', ai: false,
      chat: { who: '广州鑫铃', text: 'A1665000075 报一下' },
      steps: ['识别', '查询CRM'],
      sendFail: true,
      vininfo: VININFO[0],
      product: PRODUCT_LIST.data.list[0],
      car: VININFO[0],
    },
  ];

  /* 报价分析 */
  const ANALYSIS = {
    day: {
      quote: 86, oe: 54, vin: 32,
      trend: { quote: 12, oe: 8, vin: 4 },
      days: ['11-03','11-04','11-05','11-06','11-07','11-08','11-09','11-10','11-11','11-12','11-13','11-14','11-15','11-16','11-17'],
      series: { quote: [42,55,48,61,58,30,22,64,72,59,66,70,55,78,86], oe: [26,33,30,38,35,18,13,40,45,36,41,44,33,49,54], vin: [16,22,18,23,23,12,9,24,27,23,25,26,22,29,32] },
      top: [
        { name: '火花塞（铱金）', oe: '885625662', ct: 17 },
        { name: '节温器总成', oe: '11538635689', ct: 12 },
        { name: '上水管', oe: '1665000075', ct: 9 },
        { name: '机油滤芯', oe: '11427525309', ct: 7 },
        { name: '刹车片（前）', oe: '34116865138', ct: 5 },
      ],
    },
    month: {
      quote: 1024, oe: 652, vin: 372,
      trend: { quote: 86, oe: 51, vin: 35 },
      days: ['W1','W2','W3','W4','W5','W6','W7','W8','W9','W10'],
      series: { quote: [380,420,455,410,520,560,610,590,860,1024], oe: [242,268,290,262,332,357,388,375,548,652], vin: [138,152,165,148,188,203,222,215,312,372] },
      top: [
        { name: '火花塞（铱金）', oe: '885625662', ct: 186 },
        { name: '刹车片（前）', oe: '34116865138', ct: 152 },
        { name: '节温器总成', oe: '11538635689', ct: 138 },
        { name: '上水管', oe: '1665000075', ct: 121 },
        { name: '机油滤芯', oe: '11427525309', ct: 98 },
      ],
    },
  };

  /* 手动报价 AI 对话（聊天提取演示） */
  const AI_CHAT_SCRIPT = [
    {
      user: '帮我看下这条消息：2026-11-17 10:20:12【黄晓明】：油底壳 节温器',
      bot: { need: false, text: '已解析出 1 条询价：\n询价人：黄晓明\n配件：油底壳 / 节温器（多配件 "\\n" 分隔）\nVIN：未提供 —— 已进入手动报价查询框，请补充 VIN 或直接按名称译码。' },
    },
    {
      user: 'WBAWX3100G0L69597',
      bot: { need: false, text: 'VIN 已识别：华晨宝马 宝马X3 20iX 2016 2.0T（carBrandCode=BMW）。\n已与上一条询价合并：黄晓明 / 油底壳 / 节温器 / WBAWX3100G0L69597。\n译码结果：节温器 → OE 11538635689（4S价 1270.00）。' },
    },
    {
      user: '系统备注：上一条是【老王】发的图片',
      bot: { need: true, text: '消息已登记为「老王 / 图片」场景。提示：图片消息需紧跟一条系统备注文本说明发送人（接口文档 chat_content 规范），当前缺少图片 URL，无法执行 OCR。请在手动报价上传图片。' },
    },
  ];

  /* 手动查询结果缓存（演示同数据复用） */
  const MANUAL_CACHE = {};

  window.QQMock = {
    IMG_PRODUCT, IMG_THERMO, IMG_VIN,
    resolve(key, params = {}) {
      switch (key) {
        case 'productList': {
          const oe = String(params.number || '').toUpperCase();
          if (oe.includes('0005400017')) {
            return ok({ ...PRODUCT_LIST, data: { list: [], no_exist_oe: ['0005400017'] } });
          }
          if (oe.includes('885625662')) {
            const sc = SCENARIOS[0].product;
            return ok({ ...PRODUCT_LIST, data: { list: [{ ...PRODUCT_LIST.data.list[0], ...sc }], no_exist_oe: [] } });
          }
          return ok(PRODUCT_LIST);
        }
        case 'vininfo': return ok(VININFO);
        case 'partno': return ok(PARTNO);
        case 'partImages': return ok(PART_IMAGES);
        case 'partImagesList': return ok(PART_IMAGES_LIST);
        case 'extractParts': return ok(EXTRACT_PARTS);
        case 'txVin':
        case 'localVin': return ok('WBAWX3100G0L69597');
        case 'jqr': return ok(JQR);
        case 'zpy': return ok(ZPY);
        case 'purchaseHistory': return ok(PURCHASE_HISTORY);
        default: return ok(null);
      }
    },
    SCENARIOS, ANALYSIS, AI_CHAT_SCRIPT, MANUAL_CACHE,
    VININFO, PARTNO, PART_IMAGES_LIST, PRODUCT_LIST,
  };
})();
