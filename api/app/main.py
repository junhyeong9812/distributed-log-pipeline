from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import time

from app.database import get_db_connection
from app.hdfs_client import HDFSQueryClient

app = FastAPI(
    title="Log Query API",
    description="PostgreSQL vs Spark/HDFS 조회 성능 비교 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

hdfs_client = HDFSQueryClient()


# ==================== PostgreSQL 조회 API ====================

@app.get("/api/query/postgres/logs")
async def query_postgres_logs(
    level: Optional[str] = None,
    service: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    limit: int = Query(default=100, le=10000),
    offset: int = 0,
    order_by: str = "timestamp",
    order_dir: str = "desc"
):
    """PostgreSQL에서 로그 조회"""
    start = time.time()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 동적 쿼리 생성
    query = "SELECT id, timestamp, level, service, host, message, metadata, created_at FROM logs WHERE 1=1"
    params = []
    
    if level:
        query += " AND level = %s"
        params.append(level)
    if service:
        query += " AND service = %s"
        params.append(service)
    if start_time:
        query += " AND timestamp >= %s"
        params.append(start_time)
    if end_time:
        query += " AND timestamp <= %s"
        params.append(end_time)
    
    # 정렬
    valid_columns = ["timestamp", "level", "service", "created_at", "id"]
    if order_by not in valid_columns:
        order_by = "timestamp"
    order_dir = "DESC" if order_dir.lower() == "desc" else "ASC"
    query += f" ORDER BY {order_by} {order_dir}"
    
    # 페이징
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # 전체 카운트
    count_query = "SELECT COUNT(*) FROM logs WHERE 1=1"
    count_params = []
    if level:
        count_query += " AND level = %s"
        count_params.append(level)
    if service:
        count_query += " AND service = %s"
        count_params.append(service)
    if start_time:
        count_query += " AND timestamp >= %s"
        count_params.append(start_time)
    if end_time:
        count_query += " AND timestamp <= %s"
        count_params.append(end_time)
    
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    elapsed = time.time() - start
    
    return {
        "source": "postgresql",
        "query_time_ms": round(elapsed * 1000, 2),
        "total_count": total_count,
        "returned_count": len(rows),
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": row[0],
                "timestamp": row[1],
                "level": row[2],
                "service": row[3],
                "host": row[4],
                "message": row[5],
                "metadata": row[6],
                "created_at": row[7].isoformat() if row[7] else None
            }
            for row in rows
        ]
    }


@app.get("/api/query/postgres/logs/aggregate")
async def query_postgres_logs_aggregate(
    group_by: str = "level",
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
):
    """PostgreSQL 로그 집계 조회"""
    start = time.time()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    valid_groups = ["level", "service", "host"]
    if group_by not in valid_groups:
        group_by = "level"
    
    query = f"SELECT {group_by}, COUNT(*) as count FROM logs WHERE 1=1"
    params = []
    
    if start_time:
        query += " AND timestamp >= %s"
        params.append(start_time)
    if end_time:
        query += " AND timestamp <= %s"
        params.append(end_time)
    
    query += f" GROUP BY {group_by} ORDER BY count DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    elapsed = time.time() - start
    
    return {
        "source": "postgresql",
        "query_time_ms": round(elapsed * 1000, 2),
        "group_by": group_by,
        "data": [{"key": row[0], "count": row[1]} for row in rows]
    }


@app.get("/api/query/postgres/stats")
async def query_postgres_stats():
    """PostgreSQL 통계"""
    start = time.time()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM logs")
    logs_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM events")
    events_count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    elapsed = time.time() - start
    
    return {
        "source": "postgresql",
        "query_time_ms": round(elapsed * 1000, 2),
        "logs_count": logs_count,
        "events_count": events_count
    }


# ==================== HDFS/Spark 조회 API ====================

@app.get("/api/query/hdfs/logs")
async def query_hdfs_logs(
    level: Optional[str] = None,
    service: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    limit: int = Query(default=100, le=10000),
    order_by: str = "timestamp",
    order_dir: str = "desc"
):
    """HDFS/Spark에서 로그 조회"""
    start = time.time()
    
    result = hdfs_client.query_logs(
        level=level,
        service=service,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        order_by=order_by,
        order_dir=order_dir
    )
    
    elapsed = time.time() - start
    result["query_time_ms"] = round(elapsed * 1000, 2)
    
    return result


@app.get("/api/query/hdfs/logs/aggregate")
async def query_hdfs_logs_aggregate(
    group_by: str = "level",
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
):
    """HDFS/Spark 로그 집계 조회"""
    start = time.time()
    
    result = hdfs_client.aggregate_logs(
        group_by=group_by,
        start_time=start_time,
        end_time=end_time
    )
    
    elapsed = time.time() - start
    result["query_time_ms"] = round(elapsed * 1000, 2)
    
    return result


@app.get("/api/query/hdfs/stats")
async def query_hdfs_stats():
    """HDFS 통계"""
    start = time.time()
    
    result = hdfs_client.get_stats()
    
    elapsed = time.time() - start
    result["query_time_ms"] = round(elapsed * 1000, 2)
    
    return result


# ==================== 비교 API ====================

@app.get("/api/query/compare")
async def compare_query(
    level: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = 100
):
    """PostgreSQL vs HDFS 조회 성능 비교"""
    
    # PostgreSQL 조회
    pg_start = time.time()
    pg_result = await query_postgres_logs(level=level, service=service, limit=limit)
    pg_time = time.time() - pg_start
    
    # HDFS 조회
    hdfs_start = time.time()
    hdfs_result = await query_hdfs_logs(level=level, service=service, limit=limit)
    hdfs_time = time.time() - hdfs_start
    
    return {
        "comparison": {
            "postgresql_ms": round(pg_time * 1000, 2),
            "hdfs_ms": round(hdfs_time * 1000, 2),
            "faster": "postgresql" if pg_time < hdfs_time else "hdfs",
            "difference_ms": round(abs(pg_time - hdfs_time) * 1000, 2)
        },
        "postgresql": {
            "count": pg_result["returned_count"],
            "total": pg_result["total_count"]
        },
        "hdfs": {
            "count": hdfs_result.get("returned_count", 0),
            "total": hdfs_result.get("total_count", 0)
        }
    }


@app.get("/health")
async def health():
    return {"status": "UP"}
