from pyspark.sql import SparkSession


def get_spark_session(app_name: str) -> SparkSession:
    """Spark 세션 생성"""
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .getOrCreate()


def get_kafka_options(bootstrap_servers: str, topic: str) -> dict:
    """Kafka 읽기 옵션"""
    return {
        "kafka.bootstrap.servers": bootstrap_servers,
        "subscribe": topic,
        "startingOffsets": "earliest"
    }
