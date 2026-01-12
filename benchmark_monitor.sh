#!/bin/bash

echo "=========================================="
echo "  Write Performance 모니터링 - $(date)"
echo "=========================================="

echo ""
echo "[1] Generator 상태"
curl -s "http://192.168.55.114:30800/control/status" 2>/dev/null | jq . || echo "Generator 연결 실패"

echo ""
echo "[2] PostgreSQL 카운트"
curl -s "http://192.168.55.114:30801/api/query/postgres/stats" 2>/dev/null | jq . || echo "Query API 연결 실패"

echo ""
echo "[3] HDFS 카운트"
curl -s "http://192.168.55.114:30801/api/query/hdfs/stats" 2>/dev/null | jq . || echo "HDFS 조회 실패"

echo ""
echo "[4] Pod 상태"
kubectl get pods -n log-pipeline | grep -E "NAME|postgres|datanode|spark|backend|generator"

echo "=========================================="
