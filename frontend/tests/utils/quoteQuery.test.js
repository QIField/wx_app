import { describe, expect, it } from 'vitest'
import { detectType, quotePrice, quoteText, savePercent } from '../../src/utils/quoteQuery'

const PRODUCT = {
  product_name: '节温器总成',
  display_number: { key: 'OE', value: '11538635689' },
  cost_price: '96.21',
  store_price: '300.00',
  child: [
    { brand_name: '博世', cost_price: '96.21', stock: 5 },
    { brand_name: '马勒', cost_price: '88.00', stock: 0 },
  ],
}

describe('detectType', () => {
  it('识别 17 位 VIN（去 I/O/Q）', () => {
    expect(detectType('WBAWX3100G0L69597')).toBe('vin')
    expect(detectType('LFV3A23C8K3123456')).toBe('vin')
  })

  it('I/O/Q 出现即拒判 VIN，落回名称', () => {
    expect(detectType('IBAWX3100G0L69597')).toBe('name')
    expect(detectType('WBQWX3100G0L69597')).toBe('name')
  })

  it('识别 OE（前缀 ≤3 字母 + 6~12 数字）', () => {
    expect(detectType('11538635689')).toBe('oe')
    expect(detectType('A1665000075')).toBe('oe')
    expect(detectType('ABC123456')).toBe('oe')
  })

  it('过长/过短数字与中文都是名称', () => {
    expect(detectType('12345')).toBe('name')
    expect(detectType('12345678901234567890')).toBe('name')
    expect(detectType('节温器')).toBe('name')
    expect(detectType('')).toBe('name')
  })
})

describe('quotePrice / quoteText 改价联动', () => {
  const r = { car: { brandName: '宝马', model: 'X3', yearPattern: '2016', displacement: '2.0T' }, product: PRODUCT }

  it('未改价回退成本价，改价覆盖', () => {
    expect(quotePrice(r)).toBe('96.21')
    expect(quotePrice({ ...r, _price: '88.00' })).toBe('88.00')
  })

  it('话术：车型行 + 名称 OE + 品牌比价 + 4S 对照，缺货标注', () => {
    expect(quoteText(r)).toBe(
      '【宝马 X3 2016款 2.0T】\n'
      + '节温器总成（OE 11538635689）\n'
      + '博世 ¥96.21 / 马勒 ¥88.00(缺货)\n'
      + '4S对照价 ¥300.00',
    )
  })

  it('改价后追加报价行', () => {
    const edited = { ...r, _price: '88.00', _edited: true }
    expect(quoteText(edited).split('\n')[3]).toBe('报价 ¥88.00')
  })

  it('无产品时给出兜底文案，缺年款不出现 undefined', () => {
    expect(quoteText({ product: null })).toBe('（无匹配产品）')
    const noYear = quoteText({ car: { brandName: '宝马', model: 'X3' }, product: PRODUCT })
    expect(noYear.startsWith('【宝马 X3】')).toBe(true)
  })
})

describe('savePercent 省比', () => {
  it('按发送价计算并取整', () => {
    expect(savePercent({ product: PRODUCT })).toBe(68)
    expect(savePercent({ product: PRODUCT, _price: '300.00' })).toBe(0)
  })

  it('价格缺失或 4S 价非正返回 null', () => {
    expect(savePercent({ product: { ...PRODUCT, store_price: '' } })).toBeNull()
    expect(savePercent({})).toBeNull()
  })
})
