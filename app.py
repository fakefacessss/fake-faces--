# -*- coding: utf-8 -*-

import json
import sys
import os
import stripe
import aiohttp
import asyncio
import uvicorn
import stripe
from keras.preprocessing import image
from fastai import *
from fastai.vision import *
from io import BytesIO
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from scripts import tabledef
from scripts import forms
from scripts import helpers
from flask import Flask, redirect, url_for, render_template, request, session

export_file_url = 'https://drive.google.com/uc?export=download&id=1-Rlv4jsQa0XGsDNMvadntQhQj5r93sj-'
export_file_name = 'export.pkt'


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

classes = ['fake', 'real']
path = Path(__file__).parent

async def download_file(url, dest):
    if dest.exists(): return
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.read()
            with open(dest, 'wb') as f:
                f.write(data)

async def setup_learner():
    await download_file(export_file_url, path / export_file_name)
    try:
        learn = load_learner(path, export_file_name)
        return learn
    except RuntimeError as e:
        if len(e.args) > 0 and 'CPU-only machine' in e.args[0]:
            print(e)
            message = "\n\nThis model was trained with an old version of fastai and will not work in a CPU environment.\n\nPlease update the fastai library in your training environment and export your model again.\n\nSee instructions for 'Returning to work' at https://course.fast.ai."
            raise RuntimeError(message)
        else:
            raise


loop = asyncio.get_event_loop()
tasks = [asyncio.ensure_future(setup_learner())]
learn = loop.run_until_complete(asyncio.gather(*tasks))[0]
loop.close()


def load_image(img_path):
  img = image.load_img(img_path, target_size=(128, 128, 3))
  img = image.img_to_array(img)
  #mg = np.expand_dims(img, axis=0)
  img /= 255.
  img = pil2tensor(img,dtype= np.float32)
  return img

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
app.secret_key = os.urandom(12)  # Generic key for dev purposes only


stripe_keys = {
  'secret_key': "sk_test_DNesneMw03u6msRRwDN66lb6001kRscmfg",  # Killian's keys, I should put this in an environment variable
  'publishable_key': "pk_test_Eoego2U3SSlSNqCCMcKA7Sxx00urEsAkYE"
}

stripe.api_key = stripe_keys['secret_key']

# Heroku
#from flask_heroku import Heroku
#heroku = Heroku(app)

# ======== Routing =========================================================== #
# -------- Login ------------------------------------------------------------- #
@app.route('/', methods=['GET', 'POST'])
def login():
    if not session.get('logged_in'):
        form = forms.LoginForm(request.form)
        if request.method == 'POST':
            username = request.form['username'].lower()
            password = request.form['password']
            if form.validate():
                if helpers.credentials_valid(username, password):
                    session['logged_in'] = True
                    session['username'] = username
                    return json.dumps({'status': 'Login successful'})
                return json.dumps({'status': 'Invalid user/pass'})
            return json.dumps({'status': 'Both fields required'})
        return render_template('login.html', form=form)
    user = helpers.get_user()
    return render_template('home.html', user=user, key=stripe_keys['publishable_key'])


@app.route("/logout")
def logout():
    session['logged_in'] = False
    return redirect(url_for('login'))



@app.route('/analyze', methods=['POST', 'GET'])





#async def analyze(request):
#
#    img_data = await request.form()
#    img_bytes = await (img_data['file'].read())
#    img = open_image(BytesIO(img_bytes))
#    prediction = learn.predict(img)[0]
#
#    return render_template('image_upload.html', predictions=prediction)



def analyze():

    if 'file' not in request.files:
    	return render_template('image_upload.html', predictions=[])

    file = request.files['file']

    if file.filename == '':
    	return render_template('image_upload.html', predictions=[])

    if file and allowed_file(file.filename):
        image = load_image(file)
        print("The image was loaded")
        prediction = learn.predict(Image(image))[0]

        print("The prediction was made")
        print(prediction)
        return render_template('image_upload.html', predictions=prediction )

    return render_template('image_upload.html', predictions=[])


    #return JSONResponse({'result': str(prediction)})


@app.route('/image_upload')
def image_upload():
	return render_template('image_upload.html', predictions=[])


# -------- Signup ---------------------------------------------------------- #
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if not session.get('logged_in'):
        form = forms.LoginForm(request.form)
        if request.method == 'POST':
            username = request.form['username'].lower()
            password = helpers.hash_password(request.form['password'])
            email = request.form['email']
            if form.validate():
                if not helpers.username_taken(username):
                    helpers.add_user(username, password, email)
                    session['logged_in'] = True
                    session['username'] = username
                    return json.dumps({'status': 'Signup successful'})
                return json.dumps({'status': 'Username taken'})
            return json.dumps({'status': 'User/Pass required'})
        return render_template('login.html', form=form)
    return redirect(url_for('login'))


# -------- Settings ---------------------------------------------------------- #
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('logged_in'):
        if request.method == 'POST':
            password = request.form['password']
            if password != "":
                password = helpers.hash_password(password)
            email = request.form['email']
            helpers.change_user(password=password, email=email)
            return json.dumps({'status': 'Saved'})
        user = helpers.get_user()
        return render_template('settings.html', user=user)
    return redirect(url_for('login'))

#============== Stripe ========================================================#

@app.route('/charge', methods=['POST'])
def charge():

    # amount in cents
    amount = 500  # I don't know how much the pricing should be ...

    customer = stripe.Customer.create(
        email=request.form['stripeEmail'],
        source=request.form['stripeToken']
    )

    stripe.Charge.create(
        customer=customer.id,
        amount=amount,
        currency='usd',
        description='Flask Charge'
    )

    return redirect(url_for('image_upload'))


# ======== Main ============================================================== #
if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
