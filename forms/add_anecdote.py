from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired


class AddAnecdote(FlaskForm):
    anecdote = TextAreaField('Анекдот', render_kw={"rows": 20, "cols": 100}, validators=[DataRequired()])
    submit = SubmitField('Опубликовать')
