from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, desc, asc
from typing import Optional
import os


class HDFSQueryClient:
    def __init__(self):
        self.spark = None
        self.hdfs_path = os.getenv("HDFS_PATH", "hdfs://namenode:9000/data/logs/raw")
    
    def _get_spark(self):
        if self.spark is None:
            self.spark = SparkSession.builder \
                .appName("QueryServer") \
                .config("spark.master", os.getenv("SPARK_MASTER", "local[*]")) \
                .config("spark.hadoop.fs.defaultFS", os.getenv("HDFS_URL", "hdfs://namenode:9000")) \
                .getOrCreate()
            self.spark.sparkContext.setLogLevel("WARN")
        return self.spark
    
    # def query_logs(
    #     self,
    #     level: Optional[str] = None,
    #     service: Optional[str] = None,
    #     start_time: Optional[float] = None,
    #     end_time: Optional[float] = None,
    #     limit: int = 100,
    #     order_by: str = "timestamp",
    #     order_dir: str = "desc"
    # ):
    #     try:
    #         spark = self._get_spark()
    #
    #         df = spark.read.parquet(self.hdfs_path)
    #
    #         # 필터링
    #         if level:
    #             df = df.filter(col("level") == level)
    #         if service:
    #             df = df.filter(col("service") == service)
    #         if start_time:
    #             df = df.filter(col("timestamp") >= start_time)
    #         if end_time:
    #             df = df.filter(col("timestamp") <= end_time)
    #
    #         total_count = df.count()
    #
    #         # 정렬
    #         if order_dir.lower() == "desc":
    #             df = df.orderBy(desc(order_by))
    #         else:
    #             df = df.orderBy(asc(order_by))
    #
    #         # 제한
    #         rows = df.limit(limit).collect()
    #
    #         return {
    #             "source": "hdfs",
    #             "total_count": total_count,
    #             "returned_count": len(rows),
    #             "data": [row.asDict() for row in rows]
    #         }
    #     except Exception as e:
    #         return {
    #             "source": "hdfs",
    #             "error": str(e),
    #             "total_count": 0,
    #             "returned_count": 0,
    #             "data": []
    #         }
    def query_logs(
            self,
            level: Optional[str] = None,
            service: Optional[str] = None,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            limit: int = 100,
            order_by: str = "timestamp",
            order_dir: str = "desc",
            include_total: bool = False  # 선택적 total_count
    ):
        try:
            spark = self._get_spark()
            df = spark.read.parquet(self.hdfs_path)

            # 필터링
            if level:
                df = df.filter(col("level") == level)
            if service:
                df = df.filter(col("service") == service)
            if start_time:
                df = df.filter(col("timestamp") >= start_time)
            if end_time:
                df = df.filter(col("timestamp") <= end_time)

            # total_count는 선택적으로 (기본 비활성화)
            total_count = df.count() if include_total else -1

            # 정렬 + limit (Spark가 최적화)
            if order_dir.lower() == "desc":
                df = df.orderBy(desc(order_by))
            else:
                df = df.orderBy(asc(order_by))

            rows = df.limit(limit).collect()

            return {
                "source": "hdfs",
                "total_count": total_count,
                "returned_count": len(rows),
                "data": [row.asDict() for row in rows]
            }
        except Exception as e:
            return {
                "source": "hdfs",
                "error": str(e),
                "total_count": 0,
                "returned_count": 0,
                "data": []
            }
    
    def aggregate_logs(
        self,
        group_by: str = "level",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ):
        try:
            spark = self._get_spark()
            
            df = spark.read.parquet(self.hdfs_path)
            
            if start_time:
                df = df.filter(col("timestamp") >= start_time)
            if end_time:
                df = df.filter(col("timestamp") <= end_time)
            
            result = df.groupBy(group_by) \
                .agg(count("*").alias("count")) \
                .orderBy(desc("count")) \
                .collect()
            
            return {
                "source": "hdfs",
                "group_by": group_by,
                "data": [{"key": row[group_by], "count": row["count"]} for row in result]
            }
        except Exception as e:
            return {
                "source": "hdfs",
                "error": str(e),
                "group_by": group_by,
                "data": []
            }
    
    def get_stats(self):
        try:
            spark = self._get_spark()
            
            df = spark.read.parquet(self.hdfs_path)
            logs_count = df.count()
            
            return {
                "source": "hdfs",
                "logs_count": logs_count
            }
        except Exception as e:
            return {
                "source": "hdfs",
                "error": str(e),
                "logs_count": 0
            }
