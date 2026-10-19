FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=user . /app

USER user
ENV HOME=/home/user \
    PATH="/home/user/.local/bin:$PATH" \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "python3 -m uvicorn psx_app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
