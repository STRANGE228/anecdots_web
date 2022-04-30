import datetime
import http.client

from pyfiglet import Figlet
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
import cowsay

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_is_very_secret'

login_manager = LoginManager()
login_manager.init_app(app)

api = Api(app, catch_all_404s=True)


def main():
    db_session.global_init("db/main_base.db")
    app.run(host='localhost', port=4040, debug=True)


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
@app.route('/moder_bid/<int:num>', methods=['GET'])
@login_required
def moder_bid(num=0):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
    moder_anecdots = g.db_sess.query(Bid)
    count = moder_anecdots.count()
    lenght = count // 5 + (1 if count % 5 else 0)
    if lenght <= 7:
        pages = range(1, lenght + 1)
    else:
        pages = [1]
        pages += [num - 2, num - 1, num, num + 1, num + 2]
        pages += [lenght]
    return render_template("moder_index.html", anecdots=moder_anecdots[num * 5:(num + 1) * 5], current=num, pages=pages,
                           count=lenght)


@app.route('/users', methods=['GET'])
@app.route('/users/<int:num>', methods=['GET'])
@login_required
def users(num=0):
    name = request.query_string.decode('utf-8')[5:]
    if name:
        users = g.db_sess.query(User).filter(User.nickname.like(f'%{name}%'))
    else:
        users = g.db_sess.query(User)
    count = users.count()
    lenght = count // 5 + (1 if count % 5 else 0)
    if lenght <= 7:
        pages = range(1, lenght + 1)
    else:
        pages = [1]
        pages += [num - 2, num - 1, num, num + 1, num + 2]
        pages += [lenght]
    return render_template("users.html", users=users[num * 5:(num + 1) * 5], current=num, pages=pages, count=lenght,
                           name=name)


@app.route('/post_bid/<int:id_bid>', methods=['GET', 'POST'])
@login_required
def post_bid(id_bid):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
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


@app.route('/edit_bid/<int:id_bid>', methods=['GET', 'POST'])
@login_required
def edit_bid(id_bid):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
    form = AddAnecdote()
    if request.method == "GET":
        anecdote = g.db_sess.query(Bid).filter(Bid.id == id_bid).first()
        form.anecdote.data = anecdote.anecdote
    if form.validate_on_submit():
        bid = g.db_sess.query(Bid).filter(Bid.id == id_bid).first()
        bid.anecdote = form.anecdote.data
        g.db_sess.commit()
        return redirect('/moder_bid')
    return render_template('add_anecdote.html', form=form)


@app.route('/delete_bid/<int:id_bid>', methods=['GET', 'POST'])
@login_required
def delete_bid(id_bid):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
    bid = g.db_sess.query(Bid).filter(Bid.id == id_bid).first()
    g.db_sess.delete(bid)
    g.db_sess.commit()
    return redirect('/moder_bid')


@app.route('/add_anecdote', methods=['GET', 'POST'])
@login_required
def add_anecdote():
    form = AddAnecdote()
    if current_user.banned == 1:
        return redirect('/index')
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
    user = g.db_sess.query(User).filter(User.id == anecdote.author).first()
    if not (current_user.id == user.id or current_user.role == 'moder'):
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
        if not (current_user.id == anecdote.author or current_user.role == 'moder'):
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


@app.route('/ban_user/<int:id_user>')
@login_required
def ban_user(id_user):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
    user = g.db_sess.query(User).filter(User.id == id_user).first()
    user.banned = True
    if user.role == 'moder':
        user.role = 'user'
    anecdots = g.db_sess.query(Anecdote).filter(Anecdote.author == id_user).all()
    for anec in anecdots:
        g.db_sess.delete(anec)
    bids = g.db_sess.query(Bid).filter(Bid.author == id_user).all()
    for bid in bids:
        g.db_sess.delete(bid)
    g.db_sess.commit()
    return redirect('/users')


@app.route('/unban_user/<int:id_user>')
@login_required
def unban_user(id_user):
    if not (current_user.role == 'moder' or current_user.role == 'admin'):
        return redirect('/index')
    user = g.db_sess.query(User).filter(User.id == id_user).first()
    user.banned = False
    g.db_sess.commit()
    return redirect('/users')


@app.route('/moder_user/<int:id_user>')
@login_required
def moder_user(id_user):
    if not (current_user.role == 'admin'):
        return redirect('/index')
    user = g.db_sess.query(User).filter(User.id == id_user).first()
    user.role = 'moder'
    g.db_sess.commit()
    return redirect('/users')


@app.route('/unmoder_user/<int:id_user>')
@login_required
def unmoder_user(id_user):
    if not (current_user.role == 'admin'):
        return redirect('/index')
    user = g.db_sess.query(User).filter(User.id == id_user).first()
    user.role = 'user'
    g.db_sess.commit()
    return redirect('/users')


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
@app.route("/index/<int:num>", methods=["GET"])
def index(num=0):
    anecdots = g.db_sess.query(Anecdote)
    count = anecdots.count()
    lenght = count // 5 + (1 if count % 5 else 0)
    if lenght <= 7:
        pages = range(1, lenght + 1)
    else:
        pages = [1]
        pages += [num - 2, num - 1, num, num + 1, num + 2]
        pages += [lenght]
    return render_template("index.html", anecdots=anecdots[::-1][num * 5:(num + 1) * 5], current=num, pages=pages,
                           count=lenght)


@app.route("/user/<int:id>", methods=["GET"])
@app.route("/user/<int:id>/<int:num>", methods=["GET"])
def user(id, num=0):
    anecdots = g.db_sess.query(Anecdote).filter(Anecdote.author == id)
    count = anecdots.count()
    lenght = count // 5 + (1 if count % 5 else 0)
    if lenght <= 7:
        pages = range(1, lenght + 1)
    else:
        pages = [1]
        pages += [num - 2, num - 1, num, num + 1, num + 2]
        pages += [lenght]
    author = g.db_sess.query(User).filter(User.id == id).first()
    return render_template("user_anecdots.html", anecdots=anecdots[::-1][num * 5:(num + 1) * 5], current=num,
                           pages=pages,
                           count=lenght, author=author)


@app.route("/other_anecdotes", methods=["GET"])
def api_anecdots(num=0):
    return render_template("api_anecdote.html")


@app.route("/other_jokes", methods=["GET"])
def get_joke():
    url = "https://geek-jokes.sameerkumar.website/api?format=json"
    joke = requests.get(url).json()['joke']
    url = "https://translated-mymemory---translation-memory.p.rapidapi.com/api/get"
    querystring = {"langpair": "en|ru", "q": joke, "mt": "1", "onlyprivate": "0", "de": "a@b.c"}
    headers = {
        'x-rapidapi-key': "739924f2damsh45d96f6e1329ab9p1f3f5cjsn3faf86a331c1",
        'x-rapidapi-host': "translated-mymemory---translation-memory.p.rapidapi.com"
    }
    translated_joke = requests.request("GET", url, headers=headers, params=querystring).json()["responseData"][
        "translatedText"]
    return render_template("api_joke.html", joke=translated_joke)


@app.route("/easter", methods=["GET"])
def easter():
    joke = cowsay.get_output_string('tux', """- По радио сообщили о переходе на зимнее время, сказав, что «этой ночью,
     ровно в 03:00 нужно перевести стрелку часов на один час назад, на 02:00».
     - У всех программистов эта ночь зависла в бесконечном цикле.
     """).replace("'", "`")
    return render_template("easter.html", easter=joke)


@app.route("/thanks", methods=["GET"])
def thanks():
    text = Figlet(font='5lineoblique')
    return render_template("easter.html", easter=text.renderText('Thanks, Yandex Lyceum!'))


@app.route("/delete_user/<int:id_user>")
@login_required
def delete_user(id_user):
    if not (current_user.role == 'admin'):
        return redirect('/index')
    user = g.db_sess.query(User).filter(User.id == id_user).first()
    g.db_sess.delete(user)
    g.db_sess.commit()
    return redirect('/users')


if __name__ == '__main__':
    main()
