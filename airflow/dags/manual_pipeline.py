"""
수동 실행용 파이프라인 DAG
- 테스트용으로 수동 트리거
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'manual_log_pipeline',
    default_args=default_args,
    description='수동 실행 로그 분석 파이프라인',
    schedule_interval=None,  # 수동 트리거만
    catchup=False,
    tags=['logs', 'manual', 'batch'],
)

# 오늘 날짜
date_param = '{{ ds }}'

# Task 1: 일별 리포트
daily_report = BashOperator(
    task_id='daily_report',
    bash_command=f'''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            /opt/spark-jobs/batch/daily_report.py {date_param}
    ''',
    dag=dag,
)

# Task 2: 서비스 분석
service_analysis = BashOperator(
    task_id='service_analysis',
    bash_command=f'''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            /opt/spark-jobs/batch/service_analysis.py {date_param}
    ''',
    dag=dag,
)

daily_report >> service_analysis
