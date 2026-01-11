"""
수동 트리거용 로그 분석 파이프라인
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

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
    description='수동 트리거용 로그 분석 파이프라인',
    schedule_interval=None,
    catchup=False,
    tags=['batch', 'logs', 'manual'],
)

daily_report = BashOperator(
    task_id='daily_report',
    bash_command='''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://192.168.55.114:7077 \
            /opt/spark-jobs/batch/daily_report.py {{ ds }}
    ''',
    dag=dag,
)

service_analysis = BashOperator(
    task_id='service_analysis',
    bash_command='''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://192.168.55.114:7077 \
            /opt/spark-jobs/batch/service_analysis.py {{ ds }}
    ''',
    dag=dag,
)

daily_report >> service_analysis
