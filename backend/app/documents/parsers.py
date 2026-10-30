import io
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

LIMIT = 10 * 1024 * 1024

def parse_document(content, filename):
    """仅支持文字型PDF和DOCX段落/表格；无法读取时不得返回成功。"""
    if not content or len(content) > LIMIT:
        raise ValueError("文件为空或超过10MB工程限制")
    suffix = Path(filename).suffix.lower()
    sections = []
    if suffix == ".docx":
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("DOCX展开后过大")
            xml = archive.read("word/document.xml")
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                raise ValueError("禁止XML实体声明")
            root = ElementTree.fromstring(xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for index, paragraph in enumerate(root.findall(".//w:p", ns), 1):
                text = "".join(t.text or "" for t in paragraph.findall(".//w:t", ns)).strip()
                if text:
                    sections.append({"location": f"段落{index}", "text": text})
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("加密PDF或超过100页工程限制")
        for index, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                sections.append({"location": f"第{index}页", "text": text})
    else:
        raise ValueError("只支持PDF和DOCX")
    if not sections:
        raise ValueError("无可提取正文，请提供文字版或人工处理OCR")
    fields = {}
    for section in sections:
        for line in section["text"].splitlines():
            label, separator, value = line.partition("：")
            if separator and label.strip() and value.strip():
                key = label.strip()
                if key in fields and fields[key]["value"] != value.strip():
                    raise ValueError("重复字段值冲突，请人工核对")
                fields[key] = {"value": value.strip(), "location": section["location"]}
    return {"status": "parsed", "sections": sections, "fields": fields, "parser_version": "label-v1"}
