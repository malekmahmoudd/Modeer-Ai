# Privacy notice

The canonical text lives at [`backend/app/legal/privacy.md`](../backend/app/legal/privacy.md)
and is served by the app at `GET /api/legal/privacy`.

It sits inside the backend package rather than here because the Docker build
context is `backend/`: a copy in `docs/` would be missing from the image, and
the endpoint would work in development and 404 in production.
