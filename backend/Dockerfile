FROM python:3.12.13-slim
WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.lock
USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
