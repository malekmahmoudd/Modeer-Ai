"""Documents the app serves to users.

The privacy notice lives here rather than in ``docs/`` so it ships inside the
container image: the Docker build context is ``backend/``, so anything outside
it is simply absent at runtime, and the endpoint would 404 in production while
working perfectly in development.
"""
