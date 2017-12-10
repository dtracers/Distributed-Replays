import glob
import hashlib
import os

import argparse

import flask
import flask_login
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template, redirect
from startup import startup
from constants import UPLOAD_FOLDER

import config
from save_file import save_file
import queries

parser = argparse.ArgumentParser(description='RLBot Server.')
parser.add_argument('--port', metavar='p', type=int, default=5000,
                     help='The port to run the server on')
args = parser.parse_args()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024
app.secret_key = config.SECRET_KEY


engine, Session = startup()


# Login stuff
login_manager = flask_login.LoginManager()

login_manager.init_app(app)

users = config.users

# Replay stuff
if not os.path.isdir('replays/'):
    os.mkdir('replays/')
last_upload = {}




# Admin stuff
class LoginUser(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return

    user = LoginUser()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    if email not in users:
        return

    user = LoginUser()
    user.id = email

    # DO NOT ever store passwords in plaintext and always compare password
    # hashes using constant-time comparison!
    user.is_authenticated = request.form['password'] == users[email]['password']

    return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'GET':
        return '''
               <form action='login' method='POST'>
                <input type='text' name='email' id='email' placeholder='email'/>
                <input type='password' name='password' id='password' placeholder='password'/>
                <input type='submit' name='submit'/>
               </form>
               '''

    email = flask.request.form['email']
    if flask.request.form['password'] == users[email]['password']:
        user = LoginUser()
        user.id = email
        flask_login.login_user(user)
        return flask.redirect(flask.url_for('admin'))

    return 'Bad login'


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return 'Logged out'


@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized'


# Main stuff
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    session = Session()
    if request.method == 'POST':
        save_file(request, queries, session, last_upload, app)
    replay_data = queries.get_replay_stats(session)
    model_data = queries.get_model_stats(session)

    # fs = glob.glob(os.path.join('replays', '*'))
    # df = pd.DataFrame(fs, columns=['FILENAME'])
    # df['IP_PREFIX'] = df['FILENAME'].apply(lambda x: ".".join(x.split('\\')[-1].split('/')[-1].split('.')[0:2]))
    # stats = df.groupby(by='IP_PREFIX').count().sort_values(by='FILENAME', ascending=False).reset_index().as_matrix()
    return render_template('index.html', stats=replay_data, total=len(replay_data), model_stats=model_data)


@app.route('/config/get')
def get_config():
    if not os.path.isfile('config.cfg'):
        with open('config.cfg', 'w') as f:
            f.writelines(['[Test]', 'Please set proper config using admin interface.'])
    with open('config.cfg', 'r') as f:
        file_str = f.read()
    return jsonify({'version': 1, 'content': file_str})


@app.route('/config/set', methods=['GET', 'POST'])
@flask_login.login_required
def set_config():
    if request.method == 'POST':
        request.files['file'].save('config.cfg')
        return redirect('/admin')
    return "this doesn't do anything"


@app.route('/model/get')
def get_model():
    if os.path.isfile('recent.zip'):
        return send_file('recent.zip', as_attachment=True, attachment_filename='recent.zip')
    return jsonify([])


@app.route('/model/get/<hash>')
def get_model_hash(hash):
    fs = glob.glob('models/*.zip')
    filtered = [f for f in fs if f.startswith(hash)]
    if len(filtered) > 0:
        return send_file(filtered[0])
    return jsonify([])


@app.route('/model/set', methods=['GET', 'POST'])
@flask_login.login_required
def set_model():
    if request.method == 'POST':
        request.files['file'].save('recent.zip')
        hash = hashlib.sha1()
        if not os.path.isdir('models/'):
            os.makedirs('models/')
        with open('recent.zip', 'rb') as f:
            buf = f.read()
            hash.update(buf)
        request.files['file'].seek(0)
        request.files['file'].save(os.path.join('models', hash.hexdigest() + '.zip'))
        return redirect('/admin')
    return "this doesn't do anything"


@app.route('/model/list')
def list_model():
    if not os.path.isdir('models/'):
        os.makedirs('models/')
    return jsonify([os.path.basename(f) for f in glob.glob('models/*.zip')])


@app.route('/admin')
@flask_login.login_required
def admin():
    # 'Logged in as: ' + flask_login.current_user.id
    return render_template('admin.html')


@app.route('/replays/list')
def list_replays():
    if request.method == 'GET':
        fs = os.listdir('replays/')
        return jsonify([f.split('_')[-1] for f in fs])
    return ''


@app.route('/replays/<name>')
def get_replay(name):
    if request.method == 'GET':
        fs = os.listdir('replays/')
        filename = [f for f in fs if name in f][0]
        return send_file('replays/' + filename, as_attachment=True, attachment_filename=filename.split('_')[-1])


if __name__ == '__main__':

    app.run(host='0.0.0.0', port=args.port)
