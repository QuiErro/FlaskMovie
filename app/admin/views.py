# coding: utf8
from . import admin
from flask import render_template, redirect, url_for, flash, session, request, abort
from app.admin.forms import LoginForm, TagForm, MovieForm, PreviewForm, PwdForm, AuthForm, RoleForm, AdminForm
from app.models import Admin, Tag, Movie, Preview, User, Comment, Moviecol, Oplog, Userlog, Adminlog, Auth, Role
from functools import wraps
from app import db, app
from werkzeug.utils import secure_filename
import os
import uuid
import datetime


# 上下文应用处理器 -- 全局变量
@admin.context_processor
def tpl_extra():
    data = dict(
        online_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    return data


# 登录装饰器
def admin_login_req(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


# 权限控制装饰器
def admin_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin = Admin.query.join(
            Role
        ).filter(
            Role.id == Admin.role_id,
            Admin.id == session['admin_id']
        ).first()

        auths = list(map(lambda v: int(v), admin.role.auths.split(',')))
        auths_list = Auth.query.all()
        urls = [v.url for v in auths_list for val in auths if v.id == val]
        rule = request.url_rule
        if str(rule) not in urls and admin.is_super != 0:  # 权限不存在，且不是超级管理员
            abort(404)
        return f(*args, **kwargs)

    return decorated_function


# 修改文件名称
def change_filename(filename):
    fileinfo = os.path.splitext(filename)  # 分离包含路径的文件名与包含点号的扩展名
    filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + str(uuid.uuid4().hex + fileinfo[-1])
    print('函数中修改后的文件名：', filename)
    return filename


@admin.route('/')
@admin_login_req
def index():
    return render_template('admin/index.html')


@admin.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        data = form.data
        admin = Admin.query.filter_by(name=data['account']).first()
        if not admin.check_pwd(data['pwd']):
            flash('密码错误', category='err')
            return redirect(url_for('admin.login'))
        session['admin'] = data['account']
        session['admin_id'] = admin.id
        adminlog = Adminlog(
            admin_id=session['admin_id'],
            ip=request.remote_addr
        )
        db.session.add(adminlog)
        db.session.commit()
        return redirect(request.args.get('next') or url_for('admin.index'))
    return render_template('admin/login.html', form=form)


@admin.route('/logout')
def logout():
    session.pop('admin', None)
    session.pop('admin_id', None)
    return redirect(url_for('admin.login'))


@admin.route('/pwd', methods=['GET', 'POST'])
@admin_login_req
def pwd():
    form = PwdForm()
    if form.validate_on_submit():
        data = form.data
        admin = Admin.query.filter_by(name=session['admin']).first()
        from werkzeug.security import generate_password_hash
        admin.pwd = generate_password_hash(data['new_pwd'])
        db.session.commit()
        flash('密码修改成功，请重新登录', category='ok')
        return redirect(url_for('admin.logout'))
    return render_template('admin/pwd.html', form=form)


@admin.route('/tag/add', methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def tag_add():
    form = TagForm()
    if form.validate_on_submit():
        data = form.data
        tag_count = Tag.query.filter_by(name=data['name']).count()
        if tag_count == 1:
            flash('名称已存在', 'err')
            return redirect(url_for('admin.tag_add'))
        tag = Tag(
            name=data['name']
        )
        db.session.add(tag)
        db.session.commit()
        flash('添加成功', 'ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='添加标签：%s' % data['name']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.tag_add'))
    return render_template('admin/tag_add.html', form=form)


@admin.route('/tag/list/<int:page>', methods=['GET'])
@admin_login_req
def tag_list(page=None):
    if page is None:
        page = 1
    page_data = Tag.query.order_by(
        Tag.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/tag_list.html', page_data=page_data)


@admin.route("/tag/edit/<int:id>/", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def tag_edit(id=None):
    form = TagForm()
    tag = Tag.query.get_or_404(id)
    if form.validate_on_submit():
        data = form.data
        tag_count = Tag.query.filter_by(name=data['name']).count()
        if tag.name != data['name'] and tag_count == 1:
            flash('标签名称已存在', category='err')
            return redirect(url_for('admin.tag_edit', id=id))
        tag.name = data['name']
        db.session.commit()
        flash('标签修改成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='修改标签：%s' % data['name']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.tag_edit', id=id))
    return render_template('admin/tag_edit.html', form=form, tag=tag)


@admin.route("/tag/del/<int:id>/", methods=['GET'])
@admin_login_req
@admin_auth
def tag_del(id=None):
    if id:
        tag = Tag.query.filter_by(id=id).first_or_404()
        db.session.delete(tag)
        db.session.commit()
        flash('删除标签成功！', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='删除标签：%s' % tag.name
        )
        db.session.add(oplog)
        db.session.commit()
    return redirect(url_for('admin.tag_list', page=1))


@admin.route('/movie/add', methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def movie_add():
    form = MovieForm()
    if form.validate_on_submit():
        data = form.data

        if Movie.query.filter_by(title=data['title']).count() == 1:
            flash('电影片名已存在', category='err')
            return redirect(url_for('admin.movie_add'))

        # 获取上传文件的名称
        file_url = secure_filename(form.url.data.filename)
        file_logo = secure_filename(form.logo.data.filename)
        # 文件保存路径操作
        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        if not os.path.exists(file_save_path):
            os.makedirs(file_save_path)
            import stat
            os.chmod(file_save_path, stat.S_IRWXU)  # 授予可读写权限
        url = change_filename(file_url)
        logo = change_filename(file_logo)
        # 保存文件，需要给文件的保存路径+文件名
        form.url.data.save(file_save_path + url)
        form.logo.data.save(file_save_path + logo)

        movie = Movie(
            title=data['title'],
            url=url,
            info=data['info'],
            logo=logo,
            star=int(data['star']),
            play_num=0,
            comment_num=0,
            tag_id=int(data['tag_id']),
            area=data['area'],
            release_time=data['release_time'],
            length=data['length']
        )
        db.session.add(movie)
        db.session.commit()
        flash('添加电影成功', 'ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='添加电影：%s' % data['title']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.movie_add'))
    return render_template('admin/movie_add.html', form=form)


@admin.route('/movie/list/<int:page>', methods=['GET'])
@admin_login_req
def movie_list(page=None):
    if page is None:
        page = 1
    page_data = Movie.query.join(Tag).filter(
        Tag.id == Movie.tag_id
    ).order_by(
        Movie.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/movie_list.html', page_data=page_data)


@admin.route("/movie/del/<int:id>", methods=['GET'])
@admin_login_req
@admin_auth
def movie_del(id=None):
    if id:
        movie = Movie.query.filter_by(id=id).first_or_404()
        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        # 同时删除之前上传的文件和封面
        if os.path.exists(os.path.join(file_save_path, movie.url)):
            os.remove(os.path.join(file_save_path, movie.url))
        if os.path.exists(os.path.join(file_save_path, movie.logo)):
            os.remove(os.path.join(file_save_path, movie.logo))

        db.session.delete(movie)
        db.session.commit()
        flash('删除电影成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='删除电影：%s' % movie.title
        )
        db.session.add(oplog)
        db.session.commit()
    return redirect(url_for('admin.movie_list', page=1))


@admin.route("/movie/edit/<int:id>", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def movie_edit(id=None):
    movie = Movie.query.get_or_404(int(id))
    form = MovieForm()
    # 封面和文件可以不上传，默认为之前的文件
    form.url.validators = []
    if form.url.render_kw:
        form.url.render_kw['required'] = False
    else:
        form.url.render_kw = {'required': False}

    form.logo.validators = []
    if form.logo.render_kw:
        form.logo.render_kw['required'] = False
    else:
        form.logo.render_kw = {'required': False}

    # 赋初值
    if request.method == 'GET':
        form.title.data = movie.title
        form.info.data = movie.info
        form.star.data = movie.star
        form.tag_id.data = movie.tag_id
        form.area.data = movie.area
        form.release_time.data = movie.release_time
        form.length.data = movie.length

    if form.validate_on_submit():
        data = form.data
        if Movie.query.filter_by(title=data['title']).count() == 1 and movie.title != data['title']:
            flash('电影片名已存在', category='err')
            return redirect(url_for('admin.movie_edit', id=id))
        movie.title = data['title']
        movie.info = data['info']
        movie.star = data['star']
        movie.tag_id = data['tag_id']
        movie.area = data['area']
        movie.release_time = data['release_time']
        movie.length = data['length']

        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        if not os.path.exists(file_save_path):
            os.makedirs(file_save_path)
            import stat

            os.chmod(file_save_path, stat.S_IRWXU)  # 授予可读写权限

        # 处理电影文件逻辑：如果有新文件，先从磁盘中删除旧文件，然后保存新文件
        if form.url.data:
            # 删除以前的文件
            if os.path.exists(os.path.join(file_save_path, movie.url)):
                os.remove(os.path.join(file_save_path, movie.url))
            # 获取上传文件的名称
            file_url = secure_filename(form.url.data.filename)
            # 对上传的文件进行重命名
            movie.url = change_filename(file_url)
            # 保存文件，保存路径+文件名
            form.url.data.save(file_save_path + movie.url)

        # 处理封面图，逻辑同电影文件
        if form.logo.data:
            if os.path.exists(os.path.join(file_save_path, movie.logo)):
                os.remove(os.path.join(file_save_path, movie.logo))
            file_logo = secure_filename(form.logo.data.filename)
            movie.logo = change_filename(file_logo)
            form.logo.data.save(file_save_path + movie.logo)

        db.session.commit()
        flash('修改电影成功', 'ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='修改电影：%s' % data['title']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.movie_edit', id=id))
    return render_template('admin/movie_edit.html', form=form, movie=movie)


@admin.route("/preview/add/", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def preview_add():
    form = PreviewForm()
    data = form.data

    if form.validate_on_submit():

        if Preview.query.filter_by(title=data['title']).count() == 1:
            flash('预告标题已存在', category='err')
            return redirect(url_for('admin.preview_add'))

        file_logo = secure_filename(form.logo.data.filename)  # 获取上传文件名字
        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        if not os.path.exists(file_save_path):
            os.makedirs(file_save_path)
            import stat
            os.chmod(file_save_path, stat.S_IRWXU)  # 授予可读写权限
        logo = change_filename(file_logo)  # 文件重命名
        form.logo.data.save(file_save_path + logo)  # 保存文件

        preview = Preview(
            title=data['title'],
            logo=logo  # 只在数据库中保存文件名
        )
        db.session.add(preview)
        db.session.commit()
        flash('添加预告成功', 'ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='添加预告：%s' % data['title']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.preview_add'))

    return render_template('admin/preview_add.html', form=form)


@admin.route('preview/list/<int:page>', methods=['GET'])
@admin_login_req
def preview_list(page=None):
    if page is None:
        page = 1
    page_data = Preview.query.order_by(
        Preview.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/preview_list.html', page_data=page_data)


@admin.route("/preview/del/<int:id>", methods=['GET'])
@admin_login_req
@admin_auth
def preview_del(id=None):
    if id:
        preview = Preview.query.filter_by(id=id).first_or_404()
        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        # 同时删除之前上传的文件和封面
        if os.path.exists(os.path.join(file_save_path, preview.logo)):
            os.remove(os.path.join(file_save_path, preview.logo))

        db.session.delete(preview)
        db.session.commit()
        flash('删除电影预告成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='删除预告：%s' % preview.title
        )
        db.session.add(oplog)
        db.session.commit()
    return redirect(url_for('admin.preview_list', page=1))


@admin.route("/preview/edit/<int:id>", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def preview_edit(id=None):
    preview = Preview.query.get_or_404(int(id))
    form = PreviewForm()
    # 封面可以不上传，默认为之前的文件
    form.logo.validators = []
    if form.logo.render_kw:
        form.logo.render_kw['required'] = False
    else:
        form.logo.render_kw = {'required': False}

    # 赋初值
    if request.method == 'GET':
        form.title.data = preview.title

    if form.validate_on_submit():
        data = form.data
        if Preview.query.filter_by(title=data['title']).count() == 1 and preview.title != data['title']:
            flash('预告名已存在', category='err')
            return redirect(url_for('admin.preview_edit', id=id))
        preview.title = data['title']

        file_save_path = app.config['UP_DIR']  # 文件上传保存路径
        if not os.path.exists(file_save_path):
            os.makedirs(file_save_path)
            import stat

            os.chmod(file_save_path, stat.S_IRWXU)  # 授予可读写权限

        # 如果有新文件，先从磁盘中删除旧文件，然后保存新文件
        if form.logo.data:
            # 删除以前的文件
            if os.path.exists(os.path.join(file_save_path, preview.logo)):
                os.remove(os.path.join(file_save_path, preview.logo))
            # 获取上传文件的名称
            file_logo = secure_filename(form.logo.data.filename)
            # 对上传的文件进行重命名
            preview.logo = change_filename(file_logo)
            # 保存文件，保存路径+文件名
            form.logo.data.save(file_save_path + preview.logo)

        db.session.commit()
        flash('修改预告成功', 'ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='修改预告：%s' % data['title']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.preview_edit', id=id))
    return render_template('admin/preview_edit.html', form=form, preview=preview)


@admin.route('/user/list/<int:page>', methods=['GET'])
@admin_login_req
def user_list(page=None):
    if page is None:
        page = 1
    page_data = User.query.order_by(
        User.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/user_list.html', page_data=page_data)


@admin.route('/user/view/<int:id>', methods=['GET'])
@admin_login_req
def user_view(id=None):
    user = User.query.get_or_404(int(id))
    return render_template('admin/user_view.html', user=user)


@admin.route("/user/del/<int:id>")
@admin_login_req
@admin_auth
def user_del(id=None):
    user = User.query.get_or_404(int(id))

    file_save_path = app.config['UP_DIR'] + 'users/'
    if os.path.exists(os.path.join(file_save_path, user.face)):
        os.remove(os.path.join(file_save_path, user.face))

    db.session.delete(user)
    db.session.commit()
    flash('删除会员成功', category='ok')
    oplog = Oplog(
        admin_id=session['admin_id'],
        ip=request.remote_addr,
        reason='删除预告：%s' % user.name
    )
    db.session.add(oplog)
    db.session.commit()
    return redirect(url_for('admin.user_list', page=1))


@admin.route('/comment/list/<int:page>', methods=['GET'])
@admin_login_req
def comment_list(page=None):
    if page is None:
        page = 1
    page_data = Comment.query.join(
        Movie
    ).join(
        User
    ).filter(
        Movie.id == Comment.movie_id,
        User.id == Comment.user_id
    ).order_by(
        Comment.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/comment_list.html', page_data=page_data)


@admin.route("/comment/del/<int:id>")
@admin_login_req
@admin_auth
def comment_del(id=None):
    comment = Comment.query.get_or_404(int(id))

    db.session.delete(comment)
    db.session.commit()
    flash('删除评论成功', category='ok')
    oplog = Oplog(
        admin_id=session['admin_id'],
        ip=request.remote_addr,
        reason='删除评论：%s' % comment.content
    )
    db.session.add(oplog)
    db.session.commit()
    return redirect(url_for('admin.comment_list', page=1))


@admin.route('/moviecol/list/<int:page>', methods=['GET'])
@admin_login_req
def moviecol_list(page=None):
    if page is None:
        page = 1
    page_data = Moviecol.query.join(
        Movie
    ).join(
        User
    ).filter(
        Movie.id == Moviecol.movie_id,
        User.id == Moviecol.user_id
    ).order_by(
        Moviecol.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/moviecol_list.html', page_data=page_data)


@admin.route("/moviecol/del/<int:id>")
@admin_login_req
@admin_auth
def moviecol_del(id=None):
    moviecol = Moviecol.query.get_or_404(int(id))

    db.session.delete(moviecol)
    db.session.commit()
    flash('删除收藏成功', category='ok')
    oplog = Oplog(
        admin_id=session['admin_id'],
        ip=request.remote_addr,
        reason='删除收藏：%d-%d' % (moviecol.movie_id, moviecol.user_id)
    )
    db.session.add(oplog)
    db.session.commit()
    return redirect(url_for('admin.moviecol_list', page=1))


@admin.route('/oplog/list/<int:page>', methods=['GET'])
@admin_login_req
def oplog_list(page=None):
    if page is None:
        page = 1
    page_data = Oplog.query.join(
        Admin
    ).filter(
        Admin.id == Oplog.admin_id
    ).order_by(
        Oplog.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/oplog_list.html', page_data=page_data)


@admin.route('/adminloginlog/list/<int:page>', methods=['GET'])
@admin_login_req
def adminloginlog_list(page=None):
    if page is None:
        page = 1
    page_data = Adminlog.query.join(
        Admin
    ).filter(
        Admin.id == Adminlog.admin_id
    ).order_by(
        Adminlog.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/adminloginlog_list.html', page_data=page_data)


@admin.route('/userloginlog/list/<int:page>', methods=['GET'])
@admin_login_req
def userloginlog_list(page=None):
    if page is None:
        page = 1
    page_data = Userlog.query.join(
        User
    ).filter(
        User.id == Userlog.user_id
    ).order_by(
        Userlog.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/userloginlog_list.html', page_data=page_data)


@admin.route('/role/add', methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def role_add():
    form = RoleForm()
    if form.validate_on_submit():
        data = form.data
        role = Role(
            name=data['name'],
            auths=','.join(map(lambda item: str(item), data['auths']))  # 数字转换为字符串形式
        )
        db.session.add(role)
        db.session.commit()
        flash('角色添加成功', category='ok')
    return render_template('admin/role_add.html', form=form)


@admin.route('/role/list/<int:page>', methods=['GET'])
@admin_login_req
def role_list(page=None):
    if page is None:
        page = 1
    page_data = Role.query.order_by(
        Role.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/role_list.html', page_data=page_data)


@admin.route("/role/edit/<int:id>", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def role_edit(id=None):
    role = Role.query.get_or_404(int(id))
    form = RoleForm()
    if request.method == 'GET':
        form.auths.data = list(map(lambda v: int(v), role.auths.split(',')))
    if form.validate_on_submit():
        data = form.data
        role_count = Role.query.filter_by(name=data['name']).count()
        if role.name != data['name'] and role_count == 1:
            flash('角色名称已存在', category='err')
            return redirect(url_for('admin.role_edit', id=id))
        role.name = data['name']
        role.auths = ','.join(map(lambda item: str(item), data['auths']))
        db.session.commit()
        flash('角色修改成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='修改角色：%s' % data['name']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.role_edit', id=id))
    return render_template('admin/role_edit.html', form=form, role=role)


@admin.route("/role/del/<int:id>/", methods=['GET'])
@admin_login_req
@admin_auth
def role_del(id=None):
    if id:
        role = Role.query.get_or_404(int(id))
        db.session.delete(role)
        db.session.commit()
        flash('删除角色成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='删除角色：%s' % role.name
        )
        db.session.add(oplog)
        db.session.commit()
    return redirect(url_for('admin.role_list', page=1))


@admin.route('/auth/add', methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def auth_add():
    form = AuthForm()
    if form.validate_on_submit():
        data = form.data
        if Auth.query.filter_by(name=data['name']).count() == 1:
            flash('权限名称已存在', category='err')
            return redirect(url_for('admin.auth_add'))
        auth = Auth(
            name=data['name'],
            url=data['url']
        )
        db.session.add(auth)
        db.session.commit()
        flash('权限添加成功', category='ok')
    return render_template('admin/auth_add.html', form=form)


@admin.route('/auth/list/<int:page>', methods=['GET'])
@admin_login_req
def auth_list(page=None):
    if page is None:
        page = 1
    page_data = Auth.query.order_by(
        Auth.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/auth_list.html', page_data=page_data)


@admin.route("/auth/edit/<int:id>", methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def auth_edit(id=None):
    auth = Auth.query.get_or_404(int(id))
    form = AuthForm()
    if form.validate_on_submit():
        data = form.data
        auth_count = Auth.query.filter_by(name=data['name']).count()
        if auth.name != data['name'] and auth_count == 1:
            flash('权限名称已存在', category='err')
            return redirect(url_for('admin.auth_edit', id=id))
        auth.name = data['name']
        auth.url = data['url']
        db.session.commit()
        flash('权限修改成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='修改权限：%s' % data['name']
        )
        db.session.add(oplog)
        db.session.commit()
        return redirect(url_for('admin.auth_edit', id=id))
    return render_template('admin/auth_edit.html', form=form, auth=auth)


@admin.route("/auth/del/<int:id>/", methods=['GET'])
@admin_login_req
@admin_auth
def auth_del(id=None):
    if id:
        auth = Auth.query.get_or_404(int(id))
        db.session.delete(auth)
        db.session.commit()
        flash('删除权限成功', category='ok')
        oplog = Oplog(
            admin_id=session['admin_id'],
            ip=request.remote_addr,
            reason='删除权限：%s' % auth.name
        )
        db.session.add(oplog)
        db.session.commit()
    return redirect(url_for('admin.auth_list', page=1))


@admin.route('/admin/add', methods=['GET', 'POST'])
@admin_login_req
@admin_auth
def admin_add():
    form = AdminForm(is_super=1)
    from werkzeug.security import generate_password_hash
    if form.validate_on_submit():
        data = form.data
        if Admin.query.filter_by(name=data['name']).count() == 1:
            flash('管理员已存在！', category='err')
            return redirect(url_for('admin.admin_add'))
        admin = Admin(
            name=data['name'],
            pwd=generate_password_hash(data['pwd']),
            role_id=data['role_id'],
            is_super=1
        )
        db.session.add(admin)
        db.session.commit()
        flash('管理员添加成功', category='ok')
    return render_template('admin/admin_add.html', form=form)


@admin.route('/admin/list/<int:page>', methods=['GET'])
@admin_login_req
def admin_list(page=None):
    if page is None:
        page = 1
    page_data = Admin.query.join(
        Role
    ).filter(
        Role.id == Admin.role_id
    ).order_by(
        Admin.addtime.desc()
    ).paginate(page=page, per_page=5)
    return render_template('admin/admin_list.html', page_data=page_data)
