import datetime
import http.client
import requests
from flask import Flask, render_template, redirect, request, make_response, jsonify, g
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_restful import Api

from data import db_session
from data import __all_models
from data.anecdote import Anecdote
from data.users import User
from data.bid import Bid
from forms.add_anecdote import AddAnecdote
from forms.login import LoginForm
from forms.user import RegisterForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_is_very_secret'

login_manager = LoginManager()
login_manager.init_app(app)

api = Api(app, catch_all_404s=True)


def main():
    db_session.global_init("db/main_base.db")
    app.run(debug=True)


@app.before_request
def before_request():
    g.db_sess = db_session.create_session()


@app.teardown_request
def teardown_request(teardown):
    g.db_sess.close()


@login_manager.user_loader
def load_user(user_id):
    return g.db_sess.query(User).get(user_id)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/", methods=['GET', 'POST'])
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/index')
    form = LoginForm()
    if form.validate_on_submit():
        user = g.db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            return redirect("/index")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    users = g.db_sess.query(User)
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Пароли не совпадают")
        if g.db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Такой пользователь уже есть")
        user = User(
            nickname=form.nickname.data,
            email=form.email.data,
            dislikes=0,
            rating=0,
            role='user'
        )
        user.set_password(form.password.data)
        g.db_sess.add(user)
        g.db_sess.commit()
        return redirect('/')
    return render_template('register.html', title='Регистрация', form=form, users=users)


@app.route('/moder_bid', methods=['GET'])
@login_required
def moder_bid():
    if not(current_user.role == 'moder'):
        return redirect('index')
    moder_anecdots = g.db_sess.query(Bid)
    return render_template("moder_index.html", anecdots=moder_anecdots)


@app.route('/users', methods=['GET'])
@login_required
def users():
    if not(current_user.role == 'moder'):
        return redirect('index')
    users = g.db_sess.query(User)
    return render_template("users.html", users=users)


@app.route('/post_bid/<int:id_bid>', methods=['GET', 'POST'])
@login_required
def post_bid(id_bid):
    if not(current_user.role == 'moder'):
        return redirect('index')
    bid = g.db_sess.query(Bid).filter(Bid.id == id_bid).first()
    anecdote = Anecdote()
    anecdote.anecdote = bid.anecdote
    anecdote.author = bid.author
    anecdote.date = bid.date
    anecdote.rating = 0
    g.db_sess.add(anecdote)
    g.db_sess.delete(bid)
    g.db_sess.commit()
    return redirect('/moder_bid')


@app.route('/delete_bid/<int:id_bid>', methods=['GET', 'POST'])
@login_required
def delete_bid(id_bid):
    if not(current_user.role == 'moder'):
        return redirect('index')
    bid = g.db_sess.query(Bid).filter(Bid.id == id_bid).first()
    g.db_sess.delete(bid)
    g.db_sess.commit()
    return redirect('/moder_bid')


@app.route('/add_anecdote', methods=['GET', 'POST'])
@login_required
def add_anecdote():
    form = AddAnecdote()
    if form.validate_on_submit():
        anecdote = Bid()
        anecdote.anecdote = form.anecdote.data
        anecdote.author = current_user.id
        anecdote.date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        anecdote.rating = 0
        g.db_sess.add(anecdote)
        g.db_sess.commit()
        return redirect('/index')
    return render_template('add_anecdote.html', form=form)


@app.route("/delete_anecdote/<int:id_anecdote>")
@login_required
def del_anecdote(id_anecdote):
    anecdote = g.db_sess.query(Anecdote).filter(Anecdote.id == id_anecdote).first()
    user = g.db_sess.query(User).filter(User.id == anecdote.user.id).first()
    if not(current_user.id == user.id or current_user.role == 'moder'):
        return redirect('/index')
    user.rating = user.rating - anecdote.rating
    g.db_sess.delete(anecdote)
    g.db_sess.commit()
    return redirect('/index')


@app.route('/edit_anecdote/<int:id_anecdote>', methods=['GET', 'POST'])
@login_required
def edit_anecdote(id_anecdote):
    form = AddAnecdote()
    if request.method == "GET":
        anecdote = g.db_sess.query(Anecdote).filter(Anecdote.id == id_anecdote).first()
        if not (current_user.id == anecdote.user.id or current_user.role == 'moder'):
            return redirect('/index')
        form.anecdote.data = anecdote.anecdote
    if form.validate_on_submit():
        anecdote = g.db_sess.query(Anecdote).filter(Anecdote.id == id_anecdote).first()
        bid = Bid()
        bid.anecdote = form.anecdote.data
        bid.date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        bid.author = anecdote.author
        bid.rating = 0
        g.db_sess.delete(anecdote)
        g.db_sess.add(bid)
        g.db_sess.commit()
        return redirect('/index')
    return render_template('add_anecdote.html', form=form)


@app.errorhandler(404)
def not_found404(error):
    return make_response(jsonify({'error': 'main. Not found'}), 404)


@app.errorhandler(401)
def not_found(error):
    msg = 'Ошибка'
    if "401" in str(error):
        msg = 'Пользователь не авторизован (401)'
    elif "404" in str(error):
        msg = 'Страница не найдена (404)'
    return render_template("index.html", message=msg)


@app.route("/index", methods=["GET"])
def index():
    anecdots = g.db_sess.query(Anecdote)
    return render_template("index.html", anecdots=anecdots)


def get_info_by_ip(ip):
    response = requests.get(url=f'http://ip-api.com/json/{ip}').json()

    data = {
        'IP': response.get('query'),
        'Country': response.get('country'),
        'City': response.get('city'),
        'Lat': response.get('lat'),
        'Lon': response.get('lon')
    }

    return data['Country'], data['City'], data['Lat'], data['Lon']


def add_in_black_list(id):
    city = get_info_by_ip(request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    if city[0] is None:
        conn = http.client.HTTPConnection("ifconfig.me")
        conn.request("GET", "/ip")
        ip = str(conn.getresponse().read())
        city = get_info_by_ip(ip[2:-1])
    print(city)


if __name__ == '__main__':
    main()
