"""
일별 로그 분석 파이프라인 DAG
- 매일 새벽 2시 실행
- daily_report.py → service_analysis.py 순차 실행
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'daily_log_pipeline',
    default_args=default_args,
    description='일별 로그 분석 파이프라인',
    schedule_interval='0 2 * * *',  # 매일 새벽 2시
    catchup=False,
    tags=['logs', 'daily', 'batch'],
)

# 어제 날짜 계산
date_param = '{{ (execution_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}'

# Task 1: 일별 리포트 생성
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

# 의존성 설정: daily_report → service_analysis
daily_report >> service_analysis
