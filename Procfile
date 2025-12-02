release: python ./manage.py migrate
# Set `graceful_timeout` to shorter than the 30 second limit imposed by Heroku restarts
# Set `timeout` to shorter than the 30 second limit imposed by the Heroku router
web: gunicorn --bind 0.0.0.0:$PORT --graceful-timeout 25 --timeout 15 net_maestro.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery --app net_maestro.celery worker --loglevel INFO --without-heartbeat
