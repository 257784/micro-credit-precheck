"""将已核对的F3报告正文及既有截图排版为PDF。"""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, KeepTogether, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/delivery'
TITLE = '【待填写姓名】F3小微企业授信智能体与风控工作流编排PBL报告'
SOURCE = DIRECTORY / (TITLE + '.md')
TARGET = DIRECTORY / (TITLE + '.pdf')


def text(value):
    return escape(value).replace('`', '')


def main():
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    styles = getSampleStyleSheet()
    body = ParagraphStyle('ChineseBody', parent=styles['Normal'], fontName='STSong-Light', fontSize=10.2,
        leading=17, spaceAfter=7, wordWrap='CJK', firstLineIndent=20)
    title = ParagraphStyle('ChineseTitle', parent=body, fontSize=17, leading=25, firstLineIndent=0,
        alignment=TA_CENTER, spaceAfter=12)
    heading = ParagraphStyle('ChineseHeading', parent=body, fontSize=13, leading=20, firstLineIndent=0,
        spaceBefore=8, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#1b3a58'))
    cell = ParagraphStyle('ChineseCell', parent=body, fontSize=9, leading=14, firstLineIndent=0, spaceAfter=0)
    caption = ParagraphStyle('ChineseCaption', parent=cell, fontSize=9, leading=14, spaceAfter=8)
    doc = SimpleDocTemplate(str(TARGET), pagesize=A4, leftMargin=22*mm, rightMargin=22*mm,
        topMargin=20*mm, bottomMargin=20*mm, title='F3小微企业授信智能体与风控工作流编排PBL报告')
    width = A4[0] - 44*mm
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    story, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                row = [item.strip() for item in lines[index].strip().strip('|').split('|')]
                if not all(set(item.replace(' ', '')) <= set('-:') for item in row):
                    rows.append([Paragraph(text(item), cell) for item in row])
                index += 1
            columns = len(rows[0])
            sizes = [width * .40, width * .36, width * .24] if columns == 3 else [width * .28, width * .72]
            table = LongTable(rows, colWidths=sizes, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce8f2')),
                ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#c7cfd7')),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5),
                ('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
            story.extend([table, Spacer(1, 7)])
            continue
        if line.startswith('# '):
            story.append(Paragraph(text(line[2:]), title))
        elif line.startswith('## '):
            story.append(Paragraph(text(line[3:]), heading))
        else:
            story.append(Paragraph(text(line), body))
        index += 1
    images = [
        (ROOT/'docs/f3-knowledge-base/management/workflow-evidence/document-material-page.png', '图1 材料页面历史运行截图；非本轮实时模型结果。'),
        (ROOT/'docs/f3-knowledge-base/management/workflow-evidence/document-risk-page.png', '图2 风险预审页面历史运行截图；不代表授信决定。'),
        (ROOT/'docs/architecture/structured-assistant-browser.png', '图3 客户经理助手结构化结果页面；浏览器模拟SSE，不是真实模型输出。'),
    ]
    story.append(PageBreak())
    story.append(Paragraph('附页 页面运行与展示证据', heading))
    for path, description in images:
        if not path.is_file():
            story.append(Paragraph(text(description + '（截图缺失）'), caption))
            continue
        img = Image(str(path))
        ratio = min(width/img.imageWidth, 220*mm/img.imageHeight)
        img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
        story.append(KeepTogether([Paragraph(text(description), caption), img, Spacer(1, 10)]))
    def footer(canvas, document):
        canvas.setFont('STSong-Light', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0]/2, 11*mm, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print('PDF:', TARGET)


if __name__ == '__main__':
    main()
