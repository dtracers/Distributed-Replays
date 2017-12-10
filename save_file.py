import os
from flask import Flask, request, jsonify, send_file, render_template, redirect
import datetime
import uuid
from constants import ALLOWED_EXTENSIONS, UPLOAD_RATE_LIMIT_MINUTES
from objects import User, Replay


# Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(request, queries, session, last_upload, app):
    user = ''
    # passing username and create new user if it does not exist
    if 'username' in request.form and request.form['username'] != '':
        user = request.form['username']
        queries.create_user_if_not_exist(session, user)
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'status': 'No file uploaded'})
    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        return jsonify({'status': 'No selected file'})
    if request.remote_addr not in last_upload:
        last_upload[request.remote_addr] = datetime.datetime.now() - datetime.timedelta(minutes=15)
    time_difference = datetime.datetime.now() - last_upload[request.remote_addr]
    min_last_upload = (time_difference.total_seconds() / 60.0)
    if file and allowed_file(file.filename):  # and min_last_upload > UPLOAD_RATE_LIMIT_MINUTES:
        u = uuid.uuid4()
        filename = str(u) + '.gz'
        if user == '':
            user_id = -1
        else:
            result = session.query(User).filter(User.name == user).first()
            if result is not None:
                user_id = result.id
            else:
                user_id = -1

        if 'is_eval' in request.form:
            is_eval = request.form['is_eval']
        else:
            is_eval = False
        if 'hash' in request.form:
            model_hash = request.form['hash']
        else:
            model_hash = ''
        if 'num_players' in request.form:
            num_players = request.form['num_players']
        else:
            num_players = 0
        if 'num_my_team' in request.form:
            num_my_team = request.form['num_my_team']
        else:
            num_my_team = 0

        queries.create_model_if_not_exist(session, model_hash)

        f = Replay(uuid=u, user=user_id, ip=str(request.remote_addr),
                   model_hash=model_hash, num_team0=num_my_team, num_players=num_players, is_eval=is_eval)
        session.add(f)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        last_upload[request.remote_addr] = datetime.datetime.now()
        session.commit()
        return jsonify({'status': 'Success'})
    elif min_last_upload < UPLOAD_RATE_LIMIT_MINUTES:
        return jsonify({'status': 'Try again later', 'seconds': 60 * (UPLOAD_RATE_LIMIT_MINUTES - min_last_upload)})
    elif not allowed_file(file.filename):
        return jsonify({'status': 'Not an allowed file'})
