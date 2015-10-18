from flask import Flask
app = Flask(__name__)


from auto_updater import AutoUpdater


@app.route('/update')
def read_values():
    AutoUpdater(
        'master',
        __file__,
    ).run()
    exit(1)