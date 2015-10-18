import os
import signal
from flask import Flask
app = Flask(__name__)

from auto_updater import AutoUpdater, get_git_root


@app.route('/update')
def read_values():
    AutoUpdater(
        'master',
        get_git_root(__file__),
        'systemctl restart sensor_communicator',
    ).run(restart=True)
