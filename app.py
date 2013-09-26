from flask import (Flask, redirect, url_for, session, request, 
                   render_template, Response)
from flask_oauth import OAuth
from flask.ext.bootstrap import Bootstrap
from flaskext.csrf import csrf
import redis
import json
import os

DEBUG = True if 'DEBUG' in os.environ else False
FACEBOOK_APP_ID = os.environ['FACEBOOK_APP_ID']
FACEBOOK_APP_SECRET = os.environ['FACEBOOK_APP_SECRET']
HACK_NAME = os.environ['HACK_NAME']
REDISCLOUD_URL = os.environ['REDISCLOUD_URL']
SECRET_KEY = os.environ['SECRET_KEY']
NAMESPACE = os.environ['NAMESPACE']

app = Flask(__name__)
Bootstrap(app)
csrf(app)
app.debug = True
app.secret_key = SECRET_KEY
oauth = OAuth()

facebook = oauth.remote_app('facebook',
    base_url='https://graph.facebook.com/',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    consumer_key=FACEBOOK_APP_ID,
    consumer_secret=FACEBOOK_APP_SECRET,
    request_token_params={'scope': ''}
)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return facebook.authorize(callback=url_for('authorized',
        next=request.args.get('next') or request.referrer or None,
        _external=True))

@app.route('/authorized')
@facebook.authorized_handler
def authorized(resp):
    # TODO: handle resp is None...
    session['oauth_token'] = (resp['access_token'], '')
    return redirect(url_for('list')) # TODO: use next for redirect

@app.route('/list')
def list():

    me = facebook.get('me/?fields=id')
    print me.data
    store = redis.StrictRedis.from_url(REDISCLOUD_URL)
    print NAMESPACE
    submitter_ids = store.smembers(NAMESPACE) or ['1']
    print submitter_ids
    hacks = [json.loads(x) for x in store.mget(submitter_ids) if x]
    print hacks
    return render_template("hacks.html", hacks=hacks, hack_name=HACK_NAME, me=me.data['id'])

@app.route('/form')
def form():

    return render_template("hack.html", hack_name=HACK_NAME)

@app.route('/submit', methods=['POST'])
def submit():

    me = facebook.get('me/?fields=id')
    store = redis.StrictRedis.from_url(REDISCLOUD_URL)
    store.sadd(NAMESPACE, me.data['id'])
    hack = json.dumps({'hack_name': request.form['hack_name'],
                       'hack_url': request.form['hack_url'],
                       'hack_members': request.form['hack_members'],
                       'hack_submitter': me.data['id']}) # TODO: avoid this
    print hack
    store.set(me.data['id'], hack)
    return redirect(url_for('list'))

@app.route('/delete', methods=['POST'])
def delete():

    me = facebook.get('me/?fields=id')
    store = redis.StrictRedis.from_url(REDISCLOUD_URL)
    store.delete(me.data['id'])
    return redirect(url_for('list'))


@facebook.tokengetter
def get_facebook_oauth_token():
    return session.get('oauth_token')


if __name__ == '__main__':
    app.run()
