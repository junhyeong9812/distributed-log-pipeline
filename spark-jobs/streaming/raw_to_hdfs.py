"""
Raw 로그를 HDFS에 저장하는 Spark Streaming Job
- Kafka에서 원본 로그 읽기
- HDFS에 시간별 파티션으로 저장
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, from_unixtime,
    year, month, dayofmonth, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType,
    MapType, DoubleType
)


def create_spark_session():
    return SparkSession.builder \
        .appName("RawLogToHDFS") \
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()


def get_log_schema():
    return StructType([
        StructField("timestamp", DoubleType(), True),
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
    print("Starting Raw Log to HDFS Job")
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
        .withColumn("event_time", from_unixtime(col("timestamp")).cast("timestamp")) \
        .withColumn("year", year(col("event_time"))) \
        .withColumn("month", month(col("event_time"))) \
        .withColumn("day", dayofmonth(col("event_time"))) \
        .withColumn("hour", hour(col("event_time")))

    # HDFS에 파티션별 저장
    query = parsed_df \
        .writeStream \
        .outputMode("append") \
        .format("parquet") \
        .option("path", "hdfs://namenode:9000/data/logs/raw") \
        .option("checkpointLocation", "hdfs://namenode:9000/checkpoints/raw_logs") \
        .partitionBy("year", "month", "day", "hour") \
        .trigger(processingTime="60 seconds") \
        .start()

    print("Streaming query started. Writing raw logs to HDFS...")
    query.awaitTermination()


if __name__ == "__main__":
    main()
