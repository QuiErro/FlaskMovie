# coding: utf8
from . import home
from flask import render_template, redirect, url_for, flash, session, request
from .forms import RegisterForm, LoginFrom, UserDetailForm, PwdForm, CommentForm
from app.models import User, Userlog, Preview, Movie, Moviecol, Comment, Tag
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
from app import db, app
import uuid
from functools import wraps


def user_login_req(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('home.login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


@home.route('/<int:page>', methods=['GET'])
def index(page=None):
    if not page:
        page = 1
    tags = Tag.query.all()
    # 星级转换
    star_list = [(1, '1星'), (2, '2星'), (3, '3星'), (4, '4星'), (5, '5星')]
    stars = map(lambda x: {'num': x[0], 'info': x[1]}, star_list)
    # 年份列表
    import time
    now_year = time.localtime()[0]
    years = [year for year in range(int(now_year) - 1, int(now_year) - 5, -1)]
    page_data = Movie.query
    selected = dict()
    tag_id = request.args.get('tag_id', 0)  # 获取链接中的标签id，0为显示所有
    if int(tag_id) != 0:
        page_data = page_data.filter_by(tag_id=tag_id)
    selected['tag_id'] = tag_id

    star_num = request.args.get('star_num', 0)  # 获取星级数字，0为显示所有
    if int(star_num) != 0:
        page_data = page_data.filter_by(star=star_num)
    selected['star_num'] = int(star_num)

    time_year = request.args.get('time_year', 1)  # 1为所有日期，0为更早，月份为所选
    from sqlalchemy import extract, exists, between
    if int(time_year) == 0:
        pass
    elif int(time_year) == 1:
        page_data = page_data  # 所有年份的电影
    else:
        page_data = page_data.filter(extract('year', Movie.release_time) == time_year)  # 筛选年份
    selected['time_year'] = time_year

    play_num = request.args.get('play_num', 1)  # 1为从高到低，0为从低到好
    if int(play_num) == 1:
        page_data = page_data.order_by(
            Movie.play_num.desc()
        )
    else:
        page_data = page_data.order_by(Movie.play_num.asc())
    selected['play_num'] = play_num

    comment_num = request.args.get('comment_num', 1)  # 1为从高到低，0为从低到好
    if int(comment_num) == 1:
        page_data = page_data.order_by(
            Movie.comment_num.desc()
        )
    else:
        page_data = page_data.order_by(Movie.comment_num.asc())
    selected['comment_num'] = comment_num

    page_data = page_data.paginate(page=page, per_page=12)
    return render_template('home/index.html',
                           page_data=page_data,
                           tags=tags,
                           stars=stars,
                           now_year=now_year,
                           years=years,
                           selected=selected)


@home.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginFrom()
    if form.validate_on_submit():
        data = form.data
        user = User.query.filter_by(name=data['name']).first()
        if not user.check_pwd(data['pwd']):
            flash('密码错误', category='err')
            return redirect(url_for('home.login'))
        session['user'] = user.name
        session['user_id'] = user.id
        userlog = Userlog(
            user_id=user.id,
            ip=request.remote_addr
        )
        db.session.add(userlog)
        db.session.commit()
        return redirect(url_for('home.index', page=1))
    return render_template('home/login.html', form=form)


@home.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect(url_for('home.login'))


@home.route('/regist', methods=['GET', 'POST'])
def regist():
    form = RegisterForm()
    if form.validate_on_submit():
        data = form.data
        user = User(
            name=data['name'],
            pwd=generate_password_hash(data['pwd']),
            email=data['email'],
            phone=data['phone'],
            uuid=uuid.uuid4().hex
        )
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录', category='ok')
        return redirect(url_for('home.login'))
    return render_template('home/regist.html', form=form)


@home.route('/user', methods=['GET', 'POST'])
@user_login_req
def user():
    user = User.query.get_or_404(int(session['user_id']))
    form = UserDetailForm()
    form.face.validators = []
    form.face.render_kw = {'required': False}

    if request.method == 'GET':
        form.name.data = user.name
        form.email.data = user.email
        form.phone.data = user.phone
        form.info.data = user.info

    if form.validate_on_submit():
        data = form.data
        face_save_path = app.config['UP_DIR']
        if not os.path.exists(face_save_path):
            os.makedirs(face_save_path)  # 如果文件保存路径不存在，则创建一个多级目录
            import stat
            os.chmod(face_save_path, stat.S_IRWXU)  # 授予可读写权限

        if form.face.data:
            if user.face and os.path.exists(os.path.join(face_save_path + 'users/', user.face)):
                os.remove(os.path.join(face_save_path, user.face))
            # 获取上传文件名称
            file_face = secure_filename(form.face.data.filename)  # 前端表单设置  enctype="multipart/form-data"
            from app.admin.views import change_filename
            user.face = change_filename(file_face)
            form.face.data.save(face_save_path + 'users/' + user.face)

        if user.name != data['name'] and User.query.filter_by(name=data['name']).count() == 1:
            flash('昵称已经存在', 'err')
            return redirect(url_for('home.user'))
        user.name = data['name']

        if user.email != data['email'] and User.query.filter_by(email=data['email']).count() == 1:
            flash('邮箱已经存在', 'err')
            return redirect(url_for('home.user'))
        user.email = data['email']

        if user.phone != data['phone'] and User.query.filter_by(phone=data['phone']).count() == 1:
            flash('手机号已经存在', 'err')
            return redirect(url_for('home.user'))
        user.phone = data['phone']
        user.info = data['info']

        db.session.commit()
        flash('修改资料成功', 'ok')
        return redirect(url_for('home.user'))
    return render_template('home/user.html', form=form, user=user)


@home.route('/pwd', methods=['GET', 'POST'])
@user_login_req
def pwd():
    user = User.query.get_or_404(int(session['user_id']))
    form = PwdForm()
    if form.validate_on_submit():
        data = form.data
        if user.check_pwd(data['old_pwd']):
            user.pwd = generate_password_hash(data['new_pwd'])
            db.session.commit()
            flash('密码修改成功，请重新登录', category='ok')
            return redirect(url_for('home.login'))
        else:
            flash('旧密码不正确', category='err')
            return redirect(url_for('home.pwd'))
    return render_template('home/pwd.html', form=form)


@home.route('/comments/<int:page>', methods=['GET'])
@user_login_req
def comments(page=None):
    if not page:
        page = 1
    page_data = Comment.query.filter_by(
        user_id=int(session['user_id'])
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template('home/comments.html', page_data=page_data)


@home.route('/loginlog/<int:page>', methods=['GET'])
@user_login_req
def loginlog(page=None):
    """会员登录日志"""
    if not page:
        page = 1
    page_data = Userlog.query.filter_by(
        user_id=int(session['user_id'])
    ).order_by(
        Userlog.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template('home/loginlog.html', page_data=page_data)


@home.route('/moviecol/<int:page>', methods=['GET'])
@user_login_req
def moviecol(page=None):
    if not page:
        page = 1
    page_data = Moviecol.query.filter_by(
        user_id=int(session['user_id'])
    ).order_by(
        Moviecol.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template('home/moviecol.html', page_data=page_data)


@home.route('/moviecol/add', methods=['GET'])
@user_login_req
def moviecol_add():
    movie_id = request.args.get('movie_id', '')
    user_id = request.args.get('user_id', '')
    moviecol = Moviecol.query.filter_by(
        user_id=int(user_id),
        movie_id=int(movie_id)
    )
    if moviecol.count() == 1:
        data = dict(ok=0)
    if moviecol.count() == 0:
        moviecol = Moviecol(
            user_id=int(user_id),
            movie_id=int(movie_id)
        )
        db.session.add(moviecol)
        db.session.commit()
        data = dict(ok=1)
    import json
    return json.dumps(data)


@home.route('/animation')
def animation():
    previews = Preview.query.all()
    return render_template('home/animation.html', previews=previews)


@home.route('/search/<int:page>')
def search(page=None):
    if page is None:
        page = 1
    keyword = request.args.get('keyword', '')
    movie_count = Movie.query.filter(
        Movie.title.ilike('%' + keyword + '%')
    ).count()
    page_data = Movie.query.filter(
        Movie.title.ilike('%' + keyword + '%')
    ).order_by(
        Movie.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template('home/search.html', keyword=keyword, page_data=page_data, movie_count=movie_count)


@home.route('/play/<int:id>/<int:page>', methods=['GET', 'POST'])
def play(id=None, page=None):
    movie = Movie.query.join(Tag).filter(
        Tag.id == Movie.tag_id,
        Movie.id == int(id)
    ).first_or_404()

    if request.method == 'GET' and int(request.args.get('page', 0)) != 1:
        movie.play_num += 1  # 访问量加1
        db.session.commit()

    form = CommentForm()
    if 'user' not in session:
        form.submit.render_kw = {
            'disabled': "disabled",
            "class": "btn btn-success",
            "id": "btn-sub"
        }
    if form.validate_on_submit() and 'user' in session:
        data = form.data
        comment = Comment(
            content=data['content'],
            movie_id=movie.id,
            user_id=session['user_id']
        )
        db.session.add(comment)
        movie.comment_num += 1
        db.session.commit()
        flash('评论成功', category='ok')
        return redirect(url_for('home.play', id=movie.id, page=1))

    if page is None:
        page = 1
    page_data = Comment.query.join(
        Movie
    ).join(
        User
    ).filter(
        Movie.id == movie.id,
        User.id == Comment.user_id
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=10)
    return render_template('home/play.html', movie=movie, form=form, page_data=page_data)


# 处理弹幕消息
@home.route("/tm/v3/", methods=["GET", "POST"])
def tm():
    from flask import Response
    from app import rd
    import json
    import datetime
    import time
    resp = ''
    if request.method == "GET":  # 获取弹幕
        movie_id = request.args.get('id')  # 用id来获取弹幕消息队列，也就是js中danmaku配置的id
        key = "movie{}:barrage".format(movie_id)  # 拼接形成键值用于存放在redis队列中
        if rd.llen(key):
            msgs = rd.lrange(key, 0, 2999)
            tm_data = []
            for msg in msgs:
                msg = json.loads(msg)
                tmp_data = [msg['time'], msg['type'], msg['date'], msg['author'], msg['text']]
                tm_data.append(tmp_data)
            res = {
                "code": 0,
                # 参照官网http://dplayer.js.org/#/ 获取弹幕的消息格式
                # "data": [[6.978, 0, 16777215, "DIYgod", "1111111111111111111"],
                #          [16.338, 0, 16777215, "DIYgod", "测试"],
                #          [8.177, 0, 16777215, "DIYgod", "测试"],
                #          [7.358, 0, 16777215, "DIYgod", "1"],
                #          [15.748338, 0, 16777215, "DIYgod", "owo"]],
                "data": tm_data,
            }
        else:
            print('Redis中暂无内容')
            res = {
                "code": 1,  # 无内容code为1
                "data": []
            }
        resp = json.dumps(res)
    if request.method == "POST":  # 添加弹幕
        data = json.loads(request.get_data())
        msg = {
            "__v": 0,
            "author": data["author"],
            "time": data["time"],  # 发送弹幕视频播放进度时间
            "date": int(time.time()),  # 当前时间戳
            "text": data["text"],  # 弹幕内容
            "color": data["color"],  # 弹幕颜色
            "type": data['type'],  # 弹幕位置
            "ip": request.remote_addr,
            "_id": datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex,
            "player": data['id']
        }
        res = {
            "code": 0,
            "data": msg
        }
        resp = json.dumps(res)
        rd.lpush("movie{}:barrage".format(data['id']), json.dumps(msg))  # 将添加的弹幕推入redis的队列中
    return Response(resp, mimetype='application/json')