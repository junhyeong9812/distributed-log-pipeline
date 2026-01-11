"""
서비스 상태 분석
- 서비스별 에러율 계산
- 응답시간 분석 (metadata에서 추출)
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, avg, max, min, sum as spark_sum,
    when, round as spark_round
)
from datetime import datetime
import sys


def create_spark_session():
    return SparkSession.builder \
        .appName("ServiceAnalysis") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()


def main(target_date=None):
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    year, month, day = target_date.split("-")

    print("=" * 60)
    print(f"Service Analysis Report - {target_date}")
    print("=" * 60)

    input_path = f"hdfs://namenode:9000/data/logs/raw/year={year}/month={int(month)}/day={int(day)}"

    try:
        df = spark.read.parquet(input_path)
    except Exception as e:
        print(f"데이터 없음: {input_path}")
        spark.stop()
        return

    # 1. 서비스별 에러율
    print("\n[서비스별 에러율]")
    error_rate = df.groupBy("service") \
        .agg(
            count("*").alias("total"),
            spark_sum(when(col("level") == "ERROR", 1).otherwise(0)).alias("errors")
        ) \
        .withColumn("error_rate", 
            spark_round(col("errors") / col("total") * 100, 2)
        ) \
        .orderBy(col("error_rate").desc())
    error_rate.show()

    # 2. 호스트별 로그 분포
    print("\n[호스트별 로그 분포]")
    host_stats = df.groupBy("host") \
        .agg(
            count("*").alias("total"),
            spark_sum(when(col("level") == "ERROR", 1).otherwise(0)).alias("errors")
        ) \
        .orderBy(col("total").desc())
    host_stats.show()

    # 3. 시간대별 에러 발생 추이
    print("\n[시간대별 에러 발생]")
    hourly_errors = df.filter(col("level") == "ERROR") \
        .groupBy("hour") \
        .agg(count("*").alias("error_count")) \
        .orderBy("hour")
    hourly_errors.show(24)

    # 결과 저장
    output_path = f"hdfs://namenode:9000/data/reports/service/{target_date}"
    error_rate.write.mode("overwrite").parquet(f"{output_path}/error_rate")
    host_stats.write.mode("overwrite").parquet(f"{output_path}/host_stats")

    print(f"\n분석 결과 저장 완료: {output_path}")
    
    spark.stop()


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    main(target_date)
