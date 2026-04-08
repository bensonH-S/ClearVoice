import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FileField, SubmitField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

print("DATABASE_URL:", os.getenv("DATABASE_URL"))

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'bk-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ====================== MODELOS ======================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # pode ser anônimo
    is_anonymous = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='Pendente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(255), nullable=True)

    user = db.relationship('User', backref='reports')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ====================== FORMULÁRIOS ======================
class RegisterForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Cadastrar')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class ReportForm(FlaskForm):
    type = SelectField('Tipo', choices=[('denuncia', 'Denúncia'), ('sugestao', 'Sugestão')], validators=[DataRequired()])
    title = StringField('Título', validators=[DataRequired()])
    description = TextAreaField('Descrição', validators=[DataRequired()])
    category = SelectField('Categoria', choices=[
        ('assédio', 'Assédio'),
        ('discriminacao', 'Discriminação'),
        ('higiene', 'Higiene e Limpeza'),
        ('seguranca_alimentar', 'Segurança Alimentar'),
        ('atendimento', 'Atendimento Ruim'),
        ('qualidade_produto', 'Qualidade do Produto'),
        ('infraestrutura', 'Infraestrutura / Estrutura Física'),
        ('seguranca', 'Segurança no Estabelecimento'),
        ('transito', 'Trânsito / Estacionamento'),
        ('outros', 'Outros')
    ], validators=[DataRequired()])
    location = StringField('Localização (loja / endereço)', validators=[])
    image = FileField('Foto (opcional)')
    is_anonymous = BooleanField('Denunciar anonimamente', default=True)
    submit = SubmitField('Enviar')

# ====================== ROTAS ======================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Este email já está cadastrado!', 'danger')
            return redirect(url_for('register'))
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Cadastro realizado com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Email ou senha incorretos', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    form = ReportForm()
    if form.validate_on_submit():
        image_path = None
        if form.image.data and form.image.data.filename != '':
            file = form.image.data
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_path = f'uploads/{filename}'

        report = Report(
            user_id=current_user.id if current_user.is_authenticated and not form.is_anonymous.data else None,
            is_anonymous=form.is_anonymous.data,
            type=form.type.data,
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            location=form.location.data,
            image_path=image_path
        )
        db.session.add(report)
        db.session.commit()
        flash('✅ Denúncia enviada com sucesso! Obrigado por nos ajudar a melhorar.', 'success')
        return redirect(url_for('index'))
    return render_template('submit.html', form=form)

@app.route('/my-reports')
@login_required
def my_reports():
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).all()
    return render_template('my_reports.html', reports=reports)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))
    reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin.html', reports=reports)

@app.route('/admin/update/<int:report_id>', methods=['POST'])
@login_required
def update_status(report_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    report = Report.query.get_or_404(report_id)
    report.status = request.form.get('status')
    db.session.commit()
    flash('Status atualizado!', 'success')
    return redirect(url_for('admin'))

# ====================== CRIAÇÃO DO BANCO E ADMIN ======================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Cria admin apenas se não existir (evita duplicidade)
        admin_email = 'admin@bk.com'
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                username='admin',
                email=admin_email,
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ ADMIN CRIADO COM SUCESSO!")
            print("   → Email : admin@bk.com")
            print("   → Senha : admin123")
        else:
            print("✅ Admin já existe → admin@bk.com / admin123")

    print("\n🚀 Servidor iniciado em http://127.0.0.1:5000")
    app.run(debug=True, port=5000)