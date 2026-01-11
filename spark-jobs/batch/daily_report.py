"""
일별 로그 분석 리포트
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count
from datetime import datetime
import sys


def create_spark_session():
    return SparkSession.builder \
        .appName("DailyLogReport") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://192.168.55.114:9000") \
        .getOrCreate()


def main(target_date=None):
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    year, month, day = target_date.split("-")
    
    print("=" * 60)
    print(f"Daily Log Report - {target_date}")
    print("=" * 60)

    input_path = f"hdfs://192.168.55.114:9000/data/logs/raw/year={year}/month={int(month)}/day={int(day)}"
    
    try:
        df = spark.read.parquet(input_path)
    except Exception as e:
        print(f"데이터 없음: {input_path}")
        print(f"에러: {e}")
        spark.stop()
        return

    total_count = df.count()
    print(f"총 로그 수: {total_count}")

    print("\n[레벨별 로그 수]")
    level_stats = df.groupBy("level") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    level_stats.show()

    print("\n[서비스별 로그 수]")
    service_stats = df.groupBy("service") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    service_stats.show()

    print("\n[시간대별 로그 수]")
    hourly_stats = df.groupBy("hour") \
        .agg(count("*").alias("count")) \
        .orderBy("hour")
    hourly_stats.show(24)

    output_path = f"hdfs://192.168.55.114:9000/data/reports/daily/{target_date}"
    level_stats.write.mode("overwrite").parquet(f"{output_path}/level_stats")
    service_stats.write.mode("overwrite").parquet(f"{output_path}/service_stats")
    hourly_stats.write.mode("overwrite").parquet(f"{output_path}/hourly_stats")

    print(f"\n리포트 저장 완료: {output_path}")
    spark.stop()


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    main(target_date)
