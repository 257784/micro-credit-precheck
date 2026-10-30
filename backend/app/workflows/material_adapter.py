"""F2旧材料转为仅元数据的教学输入，不把静态摘录当作全文解析。"""

from app.schemas.materials import CheckRequest, WorkflowInput, WorkflowMaterial


def adapt_application(detail, request: CheckRequest, products: dict) -> WorkflowInput:
    product = next((code for code, name in products.items() if detail.application.product_type == name), None)
    result = WorkflowInput(
        application_id=detail.application.application_id, product=product, input_mode="legacy_metadata",
        conditions=request.conditions,
        materials=[WorkflowMaterial(
            material_id=m.material_id, application_id=m.application_id, material_type=m.material_type,
            file_name=m.file_name, version_no=m.version_no,
            parse_status="failed" if m.check_status == "解析失败" else "not_available",
            sample_excerpt=m.sample_excerpt, evidence_location=m.sample_location,
        ) for m in detail.materials],
    )
    from app.repositories.documents import DocumentStore
    from app.rules.material_config import load_configuration
    uploaded = DocumentStore().list(detail.application.application_id)
    if uploaded:
        _, rules, _ = load_configuration()
        result.input_mode = "uploaded_documents"
        for item in uploaded:
            category = item["category"]
            if category not in rules["types"]:
                raise ValueError("上传材料类别不在规则清单")
            parsed = item["parsed"]
            result.materials.append(WorkflowMaterial(
                material_id=item["id"], application_id=detail.application.application_id,
                material_type=rules["types"][category]["name"], file_name=item["filename"],
                version_no=item["version"] if item.get("unified_version") else item["version"] + max((m.version_no for m in result.materials if m.material_type == rules["types"][category]["name"] and m.mapping_source is None), default=0), canonical_code=category,
                mapping_source="上传时声明类别，正文仍须核验", parse_status=parsed["status"],
                checked_fields=rules["types"][category]["fields"] if parsed["status"] == "parsed" else [],
                extracted_fields={key: value["value"] for key, value in parsed["fields"].items()},
                evidence_location="实际文件正文；字段位置存于解析记录",
            ))
    return result
