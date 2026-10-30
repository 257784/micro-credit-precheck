"""只记录运行元数据，不记录正文或环境变量。"""
import json
import logging

logger = logging.getLogger('precheck.operations')


def record_run(operation, result):
    logger.info(json.dumps({'operation': operation, 'run_id': result.get('run_id'),
                           'application_id': result.get('application_id'),
                           'run_status': result.get('run_status')}, ensure_ascii=False))
