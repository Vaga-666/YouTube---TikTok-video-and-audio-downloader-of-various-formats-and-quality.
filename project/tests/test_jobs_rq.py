import json
import pytest

from app.utils.jobs_rq import RQBackend, KEY_TEMPLATE
import app.utils.jobs_rq as jobs_rq
import app.worker as worker


class FakeRedis:
    def __init__(self):
        self.storage = {}

    def set(self, key, value, ex=None):
        self.storage[key] = value

    def get(self, key):
        return self.storage.get(key)


class FakeQueue:
    def __init__(self, *args, **kwargs):
        self.last_call = None

    def enqueue(self, *args, **kwargs):
        self.last_call = (args, kwargs)


def test_rq_enqueue_stores_initial_status(monkeypatch):
    fake_redis = FakeRedis()
    fake_queue = FakeQueue()

    monkeypatch.setattr(jobs_rq, "redis", type("_R", (), {"from_url": staticmethod(lambda _: fake_redis)}))
    monkeypatch.setattr(jobs_rq, "Queue", lambda *a, **k: fake_queue)

    backend = RQBackend()
    job_id = backend.enqueue({"url": "https://www.youtube.com/watch?v=abc", "format": "mp4"})

    key = KEY_TEMPLATE.format(id=job_id)
    stored = json.loads(fake_redis.storage[key])
    assert stored["status"] == "queued"
    assert stored["payload"]["url"] == "https://www.youtube.com/watch?v=abc"
    assert fake_queue.last_call[0][0] == "project.app.worker.run_job"
    assert fake_queue.last_call[0][1] == job_id



def test_run_job_updates_status(monkeypatch):
    updates = []

    class FakeBackend:
        def __init__(self):
            self.job = {
                "payload": {
                    "url": "https://www.youtube.com/watch?v=abc",
                    "format": "mp4",
                    "quality": "720p",
                }
            }

        def get(self, job_id):
            return self.job if job_id == "job1" else None

        def set(self, job_id, data):
            updates.append(data)

    async def fake_process(job_id, payload, update):
        update(status="done", message="ok", progress=100, result={"filename": "x", "meta": {}})

    monkeypatch.setattr(worker, "RQBackend", lambda: FakeBackend())
    monkeypatch.setattr(worker, "process_job_async", fake_process)

    worker.run_job("job1")

    assert updates
    assert updates[-1]["status"] == "done"



def test_run_job_handles_missing_job(monkeypatch, caplog):
    class EmptyBackend:
        def get(self, job_id):
            return None

        def set(self, job_id, data):
            pass

    monkeypatch.setattr(worker, "RQBackend", lambda: EmptyBackend())

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(worker, "process_job_async", noop)

    with caplog.at_level("WARNING"):
        worker.run_job("missing")
    assert any("not found" in record.message for record in caplog.records)
