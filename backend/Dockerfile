# Pinned by digest: a rebuild gets the same Python the lock was resolved and
# tested on, not whatever 3.12-slim points at that day. To move it, see
# docs/DEPLOYMENT.md, "Backend dependency lock".
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /app
# requirements.lock pins every package, transitive ones included, to the version
# the test suite ran against, with hashes; requirements.txt only states ranges.
# --no-deps: nothing outside the lock can be pulled in; pip check proves the
# locked set is complete and consistent.
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.lock \
    && pip check \
    && useradd --create-home app
# The document-search embedding model, at a pinned revision, checked against
# SHA-256 values in fetch_model.py: a mismatch fails the build. Its own layer, so
# code changes do not download it again. The server never fetches anything.
COPY app/documents/fetch_model.py /tmp/fetch_model.py
RUN python /tmp/fetch_model.py /app/models/multilingual-e5-small && rm /tmp/fetch_model.py
COPY . .
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
