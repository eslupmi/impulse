import json
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import request, Flask, redirect, url_for

from app.im.channels import check_channels
from app.im.helpers import get_application
from app.incident.incidents import Incidents
from app.logging import logger
from app.queue.manager import QueueManager
from app.queue.queue import Queue
from app.route import generate_route
from app.webhook import generate_webhooks
from config import settings, check_updates, application

app = Flask(__name__)
route_dict = settings.get('route')
webhooks_dict = settings.get('webhooks')

route = generate_route(route_dict)
channels = check_channels(route.get_uniq_channels(), application['channels'], route.channel)
messenger = get_application(
    application,
    channels,
    route.channel
)
webhooks = generate_webhooks(webhooks_dict)
incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)
queue = Queue.recreate_queue(incidents, check_updates)

queue_manager = QueueManager(queue, messenger, incidents, webhooks, route)

# run scheduler
logger.info('Starting scheduler')
logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=queue_manager.queue_handle,
    trigger="interval",
    seconds=0.25
)
scheduler.start()
logger.info('IMPulse running!')


def create_app():
    return app


@app.route('/queue', methods=['GET'])
def route_queue_get():
    return queue.serialize(), 200


@app.route('/', methods=['POST', 'GET'])
def route_alert_post():
    if request.method == 'POST':
        alert_state = request.json
        queue.put_first(datetime.utcnow(), 'alert', None, None, alert_state)
        return alert_state, 200
    else:
        return redirect(url_for('route_incidents_get'))


@app.route('/app', methods=['POST', 'PUT'])
def route_app_buttons():
    if messenger.type == 'slack':
        payload = json.loads(request.form['payload'])
    else:
        payload = request.json
    return messenger.buttons_handler(payload, incidents, queue, route)


@app.route('/incidents', methods=['GET'])
def route_incidents_get():
    return incidents.serialize(), 200


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
