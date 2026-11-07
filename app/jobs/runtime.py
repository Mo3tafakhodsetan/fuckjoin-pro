from app.config import settings
from app.jobs.queue import JobQueue

job_queue = JobQueue(settings.redis_url, settings.daily_job_limit)
