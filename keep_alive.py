from threading import Thread
from server import app

def keep_alive():
    Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8080}).start()
