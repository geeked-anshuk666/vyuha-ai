FROM python:3.13-slim

WORKDIR /app

COPY control_plane/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV VYUHA_DB_PATH=/app/data/vyuha.db
ENV HEALTH_CHECK_INTERVAL=5
ENV MAX_AGENT_FAILURES=3
ENV GLM_API_KEY=placeholder-key
ENV GLM_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
ENV GLM_MODEL=glm-5.1

RUN mkdir -p /app/data

EXPOSE 9000

CMD ["uvicorn", "control_plane.main:app", "--host", "0.0.0.0", "--port", "9000"]
