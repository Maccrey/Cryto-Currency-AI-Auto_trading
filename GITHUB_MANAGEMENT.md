# GitHub 관리 절차

이 프로젝트의 원격 저장소는 다음 주소다.

```text
https://github.com/Maccrey/Cryto-Currency-AI-Auto_trading.git
```

## 1. Git 설치

현재 서버에 `git` 명령이 없다면 먼저 설치한다.

```bash
sudo apt-get update
sudo apt-get install -y git
```

## 2. 원격 저장소 확인

```bash
git remote -v
git branch --show-current
git status
```

원격이 없거나 다르면 아래처럼 맞춘다.

```bash
git remote add origin https://github.com/Maccrey/Cryto-Currency-AI-Auto_trading.git
# 이미 origin이 있으면
git remote set-url origin https://github.com/Maccrey/Cryto-Currency-AI-Auto_trading.git
```

## 3. 변경사항 올리기

```bash
git status
git add .
git commit -m "변경 내용 설명"
git push origin main
```

`.env`, `storage/`, `logs/`, `data/`, `*.log`, macOS 메타데이터 파일은 `.gitignore`로 제외한다.

## 4. 서버 자동 시작 파일

재부팅 자동 시작 관련 파일은 아래에 둔다.

```text
deploy/start-server.sh
deploy/systemd/crypto-auto-trading.service
```

sudo 사용이 가능한 터미널에서는 systemd 방식으로도 등록할 수 있다.

```bash
sudo install -m 0644 deploy/systemd/crypto-auto-trading.service /etc/systemd/system/crypto-auto-trading.service
sudo systemctl daemon-reload
sudo systemctl enable --now crypto-auto-trading.service
sudo systemctl status crypto-auto-trading.service
```
