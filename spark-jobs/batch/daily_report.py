"""
일별 로그 분석 리포트
- HDFS에서 특정 날짜 데이터 읽기
- 레벨별, 서비스별 집계
- 결과를 HDFS에 저장
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, avg, max, min,
    date_format, hour
)
from datetime import datetime, timedelta
import sys


def create_spark_session():
    return SparkSession.builder \
        .appName("DailyLogReport") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()


def main(target_date=None):
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # 날짜 파라미터 (기본값: 오늘)
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    year, month, day = target_date.split("-")
    
    print("=" * 60)
    print(f"Daily Log Report - {target_date}")
    print("=" * 60)

    # HDFS에서 데이터 읽기
    input_path = f"hdfs://namenode:9000/data/logs/raw/year={year}/month={int(month)}/day={int(day)}"
    
    try:
        df = spark.read.parquet(input_path)
    except Exception as e:
        print(f"데이터 없음: {input_path}")
        print(f"에러: {e}")
        spark.stop()
        return

    total_count = df.count()
    print(f"총 로그 수: {total_count}")

    # 1. 레벨별 집계
    print("\n[레벨별 로그 수]")
    level_stats = df.groupBy("level") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    level_stats.show()

    # 2. 서비스별 집계
    print("\n[서비스별 로그 수]")
    service_stats = df.groupBy("service") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    service_stats.show()

    # 3. 시간대별 집계
    print("\n[시간대별 로그 수]")
    hourly_stats = df.groupBy("hour") \
        .agg(count("*").alias("count")) \
        .orderBy("hour")
    hourly_stats.show(24)

    # 4. 레벨 + 서비스 크로스 집계
    print("\n[레벨-서비스별 로그 수]")
    cross_stats = df.groupBy("level", "service") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    cross_stats.show(20)

    # 5. 에러 로그 상세
    print("\n[ERROR 로그 메시지]")
    error_logs = df.filter(col("level") == "ERROR") \
        .select("service", "message", "host") \
        .limit(10)
    error_logs.show(truncate=False)

    # 결과 저장
    output_path = f"hdfs://namenode:9000/data/reports/daily/{target_date}"
    
    # 레벨별 통계 저장
    level_stats.write.mode("overwrite").parquet(f"{output_path}/level_stats")
    
    # 서비스별 통계 저장
    service_stats.write.mode("overwrite").parquet(f"{output_path}/service_stats")
    
    # 시간대별 통계 저장
    hourly_stats.write.mode("overwrite").parquet(f"{output_path}/hourly_stats")

    print(f"\n리포트 저장 완료: {output_path}")
    
    spark.stop()


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    main(target_date)
