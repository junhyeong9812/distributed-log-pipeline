"""
실시간 로그 집계 Spark Streaming Job
- Kafka에서 로그 읽기
- 10초 윈도우로 레벨별 집계
- HDFS에 저장
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, count,
    to_timestamp, date_format, current_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType,
    MapType
)


def create_spark_session():
    return SparkSession.builder \
        .appName("RealtimeLogAggregator") \
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()


def get_log_schema():
    """로그 데이터 스키마 정의"""
    return StructType([
        StructField("timestamp", StringType(), True),
        StructField("level", StringType(), True),
        StructField("service", StringType(), True),
        StructField("host", StringType(), True),
        StructField("message", StringType(), True),
        StructField("metadata", MapType(StringType(), StringType()), True)
    ])


def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 60)
    print("Starting Realtime Log Aggregator")
    print("Saving to HDFS: hdfs://namenode:9000/data/logs")
    print("=" * 60)

    # Kafka에서 스트림 읽기
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:9092") \
        .option("subscribe", "logs.raw") \
        .option("startingOffsets", "latest") \
        .load()

    # JSON 파싱
    log_schema = get_log_schema()

    parsed_df = kafka_df \
        .selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), log_schema).alias("data")) \
        .select("data.*") \
        .withColumn("event_time", to_timestamp(col("timestamp")))

    # 10초 윈도우로 레벨별 집계
    aggregated_df = parsed_df \
        .withWatermark("event_time", "30 seconds") \
        .groupBy(
            window(col("event_time"), "10 seconds"),
            col("level"),
            col("service")
        ) \
        .agg(count("*").alias("log_count"))

    # 결과 정리
    result_df = aggregated_df \
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("level"),
            col("service"),
            col("log_count")
        )

    # HDFS에 저장 (Parquet 포맷)
    query = result_df \
        .writeStream \
        .outputMode("update") \
        .format("parquet") \
        .option("path", "hdfs://namenode:9000/data/logs/aggregated") \
        .option("checkpointLocation", "hdfs://namenode:9000/checkpoints/logs") \
        .trigger(processingTime="30 seconds") \
        .start()

    print("Streaming query started. Writing to HDFS...")
    query.awaitTermination()


if __name__ == "__main__":
    main()
