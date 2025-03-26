Rename table
```bash
alembic revision -m [MESSAGE]
```
Run Migrations to create initial tables
```bash
alembic upgrade head
```

Example Categories: 
```
部屋, 食事, 施設, スタッフ, フロント, サービス, その他
```

### Docker 
# Docker Compose Quick Reference

This README provides instructions for working with Docker Compose.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system

You can verify installations with:
```bash
docker --version
docker compose version
```

## Basic Commands

### Starting Containers

Start your containers:
```bash
docker compose up
```

Start containers in background (detached mode):
```bash
docker compose up -d
```

### Stopping Containers

Stop and remove containers:
```bash
docker compose down
```

### Building and Rebuilding

Build images and start containers:
```bash
docker compose up --build
```

### Monitoring

View running containers:
```bash
docker compose ps
```

View logs for all services:
```bash
docker compose logs
```

View logs for a specific service:
```bash
docker compose logs [service_name]
```

Docker Exec 
```bash
docker exec -it [container_name] bash
```

If you want to change environment variables or requirements.txt
```bash
docker-compose up -d --force-recreate
```

check unused docker image, vol, network, container
```bash
docker system df
```
