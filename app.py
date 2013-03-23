from flask import (Flask, redirect, url_for, session, request, 
                   render_template, Response)
from flask_oauth import OAuth
from flask.ext.bootstrap import Bootstrap
from flaskext.csrf import csrf
import redis
import json
import os

app = Flask(__name__)
Bootstrap(app)
csrf(app)
app.debug = True if 'DEBUG' in os.environ else False
app.secret_key = os.environ['SECRET_KEY']
oauth = OAuth()

facebook = oauth.remote_app('facebook',
    base_url='https://graph.facebook.com/',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    consumer_key=os.environ['FACEBOOK_APP_ID'],
    consumer_secret=os.environ['FACEBOOK_APP_SECRET'],
    request_token_params={'scope': 
                          'user_likes,user_actions.music,user_actions.video'}
)


@app.route('/')
def index():
    return render_template("tos.html")


@app.route('/tos', methods=['POST'])
def tos():
    ingress = 'ingress' in request.form and request.form['ingress'] == 'on'
    egress = 'egress' in request.form and request.form['egress'] == 'on'
    if ingress:
        if egress:
            next = url_for('egress', _external=True)
        else:
            next = url_for('index',_external=True)
        return facebook.authorize(callback=url_for('ingress',
                                                   next=next, _external=True))
    elif egress:
        return redirect(url_for('egress'))
    else:
        return redirect(url_for('index'))


@app.route('/ingress')
@facebook.authorized_handler
def ingress(resp):

    if resp is None:
        return 'Access denied: reason=%s' % request.args['error_message']

    # Get data from facebook
    session['oauth_token'] = (resp['access_token'], '')
    me = facebook.get(
        'me/?fields=name,likes,music.listens,video.watches,fitness.runs')

    # Add user data to store
    # TODO(jim): asynchronous ingress in worker
    store = redis.StrictRedis.from_url(os.environ['MYREDIS_URL'])
    store.sadd(os.environ['HACK_NAME'], me.data['id'])
    store.set(me.data['id'], json.dumps(me.data))

    return redirect(request.args['next'])

@app.route('/egress')
def egress():

    store = redis.StrictRedis.from_url(os.environ['MYREDIS_URL'])

    # Get aggregate data from store
    # TODO(jim): asynchronous aggregation in worker
    members = store.smembers(os.environ['HACK_NAME'])
    member_data = store.mget(members) if members else []
    aggregate_data = '[' + ','.join(member_data) + ']'
    
    return Response(aggregate_data, mimetype='application/json') 


@facebook.tokengetter
def get_facebook_oauth_token():
    return session.get('oauth_token')


if __name__ == '__main__':
    app.run()
