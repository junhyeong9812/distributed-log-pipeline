#!/bin/bash
set -e

echo "=========================================="
echo "  Distributed Log Pipeline - Worker Setup"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수: 성공 메시지
success() {
    echo -e "${GREEN}✔ $1${NC}"
}

# 함수: 경고 메시지
warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 함수: 에러 메시지
error() {
    echo -e "${RED}✘ $1${NC}"
}

# 1. 시스템 업데이트
echo ""
echo "[1/5] 시스템 업데이트..."
sudo apt update && sudo apt upgrade -y
success "시스템 업데이트 완료"

# 2. 필수 패키지 설치
echo ""
echo "[2/5] 필수 패키지 설치..."
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git
success "필수 패키지 설치 완료"

# 3. Docker 설치
echo ""
echo "[3/5] Docker 설치..."
if command -v docker &> /dev/null; then
    warn "Docker가 이미 설치되어 있습니다"
    docker --version
else
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    success "Docker 설치 완료"
fi

# 4. Docker Compose 확인 (V2는 Docker에 포함)
echo ""
echo "[4/5] Docker Compose 확인..."
if docker compose version &> /dev/null; then
    success "Docker Compose V2 사용 가능"
    docker compose version
else
    error "Docker Compose V2를 사용할 수 없습니다"
    exit 1
fi

# 5. 프로젝트 디렉토리 생성
echo ""
echo "[5/5] 프로젝트 디렉토리 생성..."
mkdir -p ~/project
success "프로젝트 디렉토리 생성 완료: ~/project"

# 완료 메시지
echo ""
echo "=========================================="
echo -e "${GREEN}  Worker 설정 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "  1. 로그아웃 후 다시 로그인 (Docker 그룹 적용)"
echo "  2. 프로젝트 Clone:"
echo "     cd ~/project"
echo "     git clone <your-repo-url> distributed-log-pipeline"
echo ""
echo "  3. Worker 서비스 시작:"
echo "     cd distributed-log-pipeline/deploy"
echo "     docker compose -f docker-compose.worker.yml up -d"
echo ""
