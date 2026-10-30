"""文件业务入口：类别校验、存储和查询，不生成HTTP响应。"""


class DocumentService:
    def upload(self, application_id, category, filename, content):
        from app.repositories.documents import DocumentStore
        from app.rules.material_config import load_configuration
        _, rules, _ = load_configuration()
        if category not in rules['types']:
            raise ValueError('未知材料类别')
        return DocumentStore().upload(application_id, category, filename, content)

    def list(self, application_id):
        from app.repositories.documents import DocumentStore
        return DocumentStore().list(application_id)

    def download(self, application_id, document_id):
        from app.repositories.documents import DocumentStore
        store = DocumentStore()
        item = store.get(application_id, document_id)
        return (store.directory / item['id'], item['filename']) if item else None
