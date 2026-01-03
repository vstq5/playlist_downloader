"""Background worker entrypoint.

This project is currently configured for Option A (Render free, zero-cost):
downloads run inside the web service using FastAPI BackgroundTasks.

The previous separate worker mode was removed from the default deployment config.
"""
