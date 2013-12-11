from mistral import config
from mistral.engine.scalable import engine
from mistral.openstack.common import log as logging

config.parse_args()
logging.setup("mistral")

tasks = []

for i in range(1000000):
    tasks.append({"id": i, "name": "task%s" % i, "execution_id": 1})

engine._notify_task_executors(tasks)
