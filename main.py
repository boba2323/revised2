from __future__ import annotations
from datetime import timedelta
from dotenv import load_dotenv
import os
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from typing import List
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
URI = os.getenv("SQLALCHEMY_DATABASE_URI")


app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=1)
ckeditor = CKEditor(app)

login_manager = LoginManager()
login_manager.init_app(app)
Bootstrap5(app)

@login_manager.user_loader
def load_user(user_id):
    user_object = db.get_or_404(User, user_id)
    return user_object


class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = URI
db = SQLAlchemy(model_class=Base)
db.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    author: Mapped["User"] = relationship(back_populates="blogpost")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments: Mapped[List["Comments"]] = relationship(back_populates="parent_post")


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blogpost: Mapped[List["BlogPost"]] = relationship(back_populates="author")
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    comments: Mapped[List["Comments"]] = relationship(back_populates="author")


class Comments(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    author: Mapped["User"] = relationship(back_populates="comments")
    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))
    parent_post: Mapped["BlogPost"] = relationship(back_populates="comments")


with app.app_context():
    db.create_all()


def admin_only(func):
    @wraps(func)
    def wrapper_(*args, **kwargs):
        if current_user.get_id() != "1":
            return abort(403)
        return func(*args, **kwargs)
    return wrapper_


@app.route('/register', methods=["GET", "POST"])
def register():
    reg_form = RegisterForm()
    name = reg_form.name.data
    email = reg_form.email.data
    password = reg_form.password.data
    user_exists = db.session.execute(db.select(User).filter_by(email=email)).scalar()
    if reg_form.validate_on_submit():
        if not user_exists:
            hash_and_salted_password = generate_password_hash(
                password=password,
                method='pbkdf2:sha256',
                salt_length=8
            )
            new_user = User(
                email=reg_form.email.data,
                password=hash_and_salted_password,
                name=reg_form.name.data
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
        else:
            flash("You have already registered with this email")
            return redirect(url_for("login"))
    return render_template("register.html", form=reg_form, user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    loginform = LoginForm()
    if loginform.validate_on_submit():
        user_row = db.session.execute(db.select(User).filter_by(email=loginform.email.data)).scalar()
        if not user_row:
            flash("The email is invalid!")
            return redirect(url_for("login"))
        elif not check_password_hash(user_row.password, loginform.password.data):
            flash("Your password is invalid!")
            return redirect(url_for("login"))
        else:
            login_user(user_row)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html", form=loginform, user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    print(current_user)
    user_exist = db.session.execute(db.select(User)).scalars().all()
    if '_id' in session and not user_exist:
        session.clear()

    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html",
                           user=current_user,
                           all_posts=posts,
                           is_logged_in=current_user.is_authenticated,
                           is_admin=current_user.get_id())


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in before you can comment!")
            return redirect(url_for("login"))
        comment_text = comment_form.comment.data
        new_comment = Comments(
            text=comment_text,
            author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post,
                           user=current_user,
                           is_logged_in=current_user.is_authenticated, form=comment_form,
                           comments=requested_post.comments
                           )


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, user=current_user,
                           is_logged_in=current_user.is_authenticated
                           )


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form,
                           is_edit=True,user=current_user,
                           is_logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    comm = db.session.execute(db.select(Comments)).scalars().all()
    for com in comm:
        if com.post_id == post_id:
            db.session.delete(com)
            db.session.commit()
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html",
                           is_logged_in=current_user.is_authenticated,user=current_user,
                           )


@app.route("/contact")
def contact():
    return render_template("contact.html",
                           is_logged_in=current_user.is_authenticated, user=current_user,
                           )


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html",user=current_user, is_logged_in=current_user.is_authenticated
                           )


if __name__ == "__main__":
    app.run(debug=True, port=5002)
