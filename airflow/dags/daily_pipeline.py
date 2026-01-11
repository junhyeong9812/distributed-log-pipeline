"""
일별 로그 분석 파이프라인
매일 새벽 2시에 실행
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'daily_log_pipeline',
    default_args=default_args,
    description='일별 로그 분석 파이프라인',
    schedule_interval='0 2 * * *',
    catchup=False,
    tags=['batch', 'daily', 'logs'],
)

daily_report = BashOperator(
    task_id='daily_report',
    bash_command='''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://192.168.55.114:7077 \
            /opt/spark-jobs/batch/daily_report.py {{ (execution_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}
    ''',
    dag=dag,
)

service_analysis = BashOperator(
    task_id='service_analysis',
    bash_command='''
        docker exec spark-master /spark/bin/spark-submit \
            --master spark://192.168.55.114:7077 \
            /opt/spark-jobs/batch/service_analysis.py {{ (execution_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}
    ''',
    dag=dag,
)

daily_report >> service_analysis
