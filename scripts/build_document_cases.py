"""生成可上传的完整OOXML教学文件，无外部文档库依赖。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "mock_data/document_cases"
NAME = "澄川青禾包装科技有限公司（虚构）"
COMMON = "本文件全部主体、交易和标识均为虚构教学设定，不是真实登记证明、合同或融资承诺。"
CASES = {
 "M-C01": ("授信申请表", {"主体名称": NAME, "统一社会信用代码": "DEMO-QH-001（教学标识）", "申请产品": "设备更新贷（教学产品）", "申请金额": "120000", "金额单位": "元", "用途": "购置两台全新QH-P200包装设备，用于现有纸盒封装工序", "联系人": "教学联系人林禾", "提交日期": "2026-10-28", "真实性确认": "本教学申请与所附虚构材料保持一致；真实业务须另行核验原件"}),
 "M-C02": ("主体登记资料", {"主体名称": NAME, "统一社会信用代码": "DEMO-QH-001（教学标识）", "主体类型": "有限责任公司（虚构）", "经营范围": "纸制包装加工及包装服务", "经营场所": "澄川教学园区三号厂房（虚构地点）"}),
 "M-C03": ("经营情况说明", {"主要业务": "为教学示例食品企业加工纸盒，现有人工装盒及半自动封装工序", "经营场所": "澄川教学园区三号厂房", "主要交易情况": "采用按批交付、月度对账方式；本材料不作为具体营业收入证明", "融资需求": "申请120000元购置设备，改善封装工序，设备投产收益属于预测，不作收益保证"}),
 "M-E01": ("设备采购计划", {"设备名称": "全新自动包装设备", "规格": "QH-P200，每分钟20盒", "数量": "2", "单价": "60000", "总价": "120000", "供应商": "澄川示例设备制造有限公司（虚构）", "采购时间": "2026-11-10", "安装安排": "2026-11-15在三号厂房安装，由供应商培训操作人员", "费用构成": "总价含税、运输及安装，不另收附加费用", "设备新旧属性": "全新", "币种": "CNY", "金额单位": "元", "含税口径": "含税", "报价编号": "QH-Q-20261028"}),
 "D-QUOTE": ("供应商报价单", {"供应商": "澄川示例设备制造有限公司（虚构）", "规格": "QH-P200，每分钟20盒", "数量": "2", "单价": "60000", "价格": "120000", "日期": "2026-10-28", "币种": "CNY", "金额单位": "元", "含税口径": "含税", "费用构成": "总价含税、运输及安装，不另收附加费用", "报价编号": "QH-Q-20261028", "交易说明": "本报价仅为教学询价文件，不证明签约、付款或设备交付"}),
 "D-UNSIGNED": ("未签约说明", {"申请主体": NAME, "报价编号": "QH-Q-20261028", "未签约原因": "正在核实安装条件，采购目前处于询价阶段，尚未签订采购合同", "后续安排": "完成设备与场地适配核对后再决定是否签约；报价不等于合同成立"}),
}


def write_docx(path, title, fields):
    def paragraph(text, title=False):
        style = '<w:pPr><w:pStyle w:val="Title"/></w:pPr>' if title else ''
        return '<w:p>' + style + '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>'
    body = paragraph(title, True) + paragraph(COMMON) + ''.join(paragraph(k + '：' + v) for k, v in fields.items())
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:bottom="1134" w:left="1134" w:right="1134"/></w:sectPr></w:body></w:document>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', xml)


def main():
    manifest = []
    for code, (title, fields) in CASES.items():
        filename = code + '-' + title + '.docx'
        write_docx(OUT / 'normal' / filename, title, fields)
        manifest.append({"category": code, "file": 'normal/' + filename})
        # PDF为同源正文的独立文字版本，不声称是Word版式转换。
        import pymupdf
        pdf = pymupdf.open(); page = pdf.new_page(width=595, height=842)
        page.insert_font(fontname='teaching', fontfile='C:/Windows/Fonts/msyh.ttc')
        y = 50
        for text in [title, COMMON] + [key+'：'+value for key, value in fields.items()]:
            for start in range(0, len(text), 38):
                page.insert_text((45,y), text[start:start+38], fontname='teaching', fontsize=11)
                y += 20
            y += 6
        pdf.subset_fonts()
        pdf.save(str(OUT/'normal'/(code+'-'+title+'.pdf')), garbage=4, deflate=True)
        page.get_pixmap().save(str(OUT/(code+'-preview.png')))
        pdf.close()
    write_docx(OUT / 'invalid_content/供应商报价单.docx', '供应商报价单', {"产品介绍": "本设备适用于纸盒包装，具有自动输送功能。本文仅为宣传介绍，未提供具体交易报价。"})
    fields = dict(CASES['D-QUOTE'][1]); fields.update(价格='150000', 单价='75000')
    write_docx(OUT / 'amount_difference/供应商报价单.docx', '供应商报价单', fields)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    seed = ROOT / 'mock_data/seed.json'
    data = json.loads(seed.read_text(encoding='utf-8'))
    data['enterprises'] = [x for x in data['enterprises'] if x['enterprise_id'] != 'ENT-DOC-TEST']
    data['enterprises'].append(dict(enterprise_id='ENT-DOC-TEST', enterprise_name=NAME, industry='包装加工', registered_region='教学园区', created_at='2026-10-28T00:00:00+08:00'))
    for item in data['applications']:
        if item['application_id'] in ('APP-DOC-NORMAL','APP-DOC-CONTENT','APP-DOC-AMOUNT'):
            item.update(product_type='设备更新贷（教学产品）', status='待风控复核', account_manager_name='教学客户经理')
    seed.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
