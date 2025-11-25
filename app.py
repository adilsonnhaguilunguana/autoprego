from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from threading import Lock
import os, time
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import traceback
from sqlalchemy import func

ULTIMO_LDR = {"valorLuz": 0, "R1": 0}

# ✅✅✅ CONFIGURAÇÃO EXCLUSIVA PARA RAILWAY
print("🚀 Configurando para Railway...")

app = Flask(__name__)
app.config.from_object(Config)

# ✅ DATABASE URL DO RAILWAY (OBRIGATÓRIO)
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("❌ ERRO: DATABASE_URL não encontrada. Configure no Railway!")
    # Pode continuar para testes, mas não funcionará sem database
    database_url = 'sqlite:///temp.db'  # Fallback temporário

# Converter postgres:// para postgresql:// (Railway usa postgres://)
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
print(f"✅ Database URL configurada para Railway")

# ✅ CONFIGURAÇÕES OTIMIZADAS PARA RAILWAY
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # Respostas mais rápidas
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
}

# O resto do código continua igual...
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'autenticacao'

# ==========================================================
# CRIAÇÃO AUTOMÁTICA DAS TABELAS NO RAILWAY (Flask 3.0+)
# ==========================================================
tabelas_criadas = False

@app.before_request
def criar_tabelas_automaticamente():
    global tabelas_criadas
    if not tabelas_criadas:
        try:
            print("📦 Criando tabelas no PostgreSQL...")
            db.create_all()
            tabelas_criadas = True
            print("✅ Tabelas criadas com sucesso!")
        except Exception as e:
            print("❌ Erro ao criar tabelas:", e)

# -----------------------------
# Rotas Básicas
# -----------------------------
@app.route('/')
@app.route('/base')
@login_required
def base():
    return render_template('base.html', now=datetime.now())
# -----------------------------
# Configurações e dados globais
# -----------------------------
API_KEYS = {"SUA_CHAVE_API_SECRETA": "ESP8266"}

dados_pzem = {
    "pzem1": {"voltage":0, "current": 0, "power": 0, "energy": 0, "frequency": 0, "pf": 0, "limite": 1000, "conectado": False, "ultima_atualizacao": None},
    "pzem2": {"voltage":0, "current": 0, "power": 0, "energy": 0, "frequency": 0, "pf": 0, "limite": 1000, "conectado": False, "ultima_atualizacao": None}
}
ultimo_consumo_conhecido = {"pzem1": 0.0, "pzem2": 0.0}
comandos_pendentes = []
dados_lock = Lock()

# -----------------------------
# Modelos de Banco de Dados
# -----------------------------
class DailyPeak(db.Model):
    __tablename__ = "daily_peaks"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, index=True)
    pzem_id = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    time = db.Column(db.Time, nullable=False)

class WeeklyPeak(db.Model):
    __tablename__ = "weekly_peaks"
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, index=True)  # primeiro dia da semana
    pzem_id = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    time = db.Column(db.Time, nullable=False)

class MonthlyPeak(db.Model):
    __tablename__ = "monthly_peaks"
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, index=True)  # 1 a 12
    year = db.Column(db.Integer, index=True)
    pzem_id = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    time = db.Column(db.Time, nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

class EnergyData(db.Model):
    __tablename__ = 'energy_data'
    id = db.Column(db.Integer, primary_key=True)
    pzem_id = db.Column(db.Integer, nullable=False)
    voltage = db.Column(db.Float, nullable=False)
    current = db.Column(db.Float, nullable=False)
    power = db.Column(db.Float, nullable=False)
    energy = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.Float, nullable=False)
    pf = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
class Rele(db.Model):
    __tablename__ = 'reles'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    pzem_id = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.Boolean, default=False)
    prioridade = db.Column(db.Integer, default=3)
    limite_individual = db.Column(db.Float, default=5.0)
    modo_automatico = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ✅ NOVOS CAMPOS: Controle de sincronização
    ultima_alteracao_manual = db.Column(db.DateTime, default=datetime.utcnow)
    ultima_sincronizacao_esp = db.Column(db.DateTime, default=datetime.utcnow)
    bloqueado_para_sincronizacao = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "pzem_id": self.pzem_id,
            "estado": self.estado,
            "prioridade": self.prioridade,
            "limite_individual": self.limite_individual,
            "modo_automatico": self.modo_automatico,
            "modo_desc": "Automático" if self.modo_automatico else "Manual",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "bloqueado_para_sincronizacao": self.bloqueado_para_sincronizacao
        }

# Adicione esta classe após a classe Rele
class ReleLog(db.Model):
    __tablename__ = 'reles_logs'
    id = db.Column(db.Integer, primary_key=True)
    rele_id = db.Column(db.Integer, nullable=False)
    estado_anterior = db.Column(db.Boolean)
    estado_novo = db.Column(db.Boolean)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(100))  # 'manual', 'automatico', 'saldo_baixo', 'sistema'
    modo_operacao = db.Column(db.String(20))  # 'manual', 'automatico'
    saldo_kwh = db.Column(db.Float)  # Saldo no momento da mudança
    
    def to_dict(self):
        return {
            "id": self.id,
            "rele_id": self.rele_id,
            "estado_anterior": "LIGADO" if self.estado_anterior else "DESLIGADO",
            "estado_novo": "LIGADO" if self.estado_novo else "DESLIGADO",
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "motivo": self.motivo,
            "modo_operacao": self.modo_operacao,
            "saldo_kwh": self.saldo_kwh
        }

class Configuracao(db.Model):
    __tablename__ = 'configuracoes'
    id = db.Column(db.Integer, primary_key=True)
    
    # ==========================================================
    # CONFIGURAÇÕES DE LIMITES E CONSUMO
    # ==========================================================
    limite_pzem1 = db.Column(db.Float, default=1000.0)
    limite_pzem2 = db.Column(db.Float, default=1000.0)
    preco_kwh = db.Column(db.Float, default=0.75)
    saldo_kwh = db.Column(db.Float, default=0.0)
    prioridade_minima_emergencia = db.Column(db.Integer, default=3)
    
    # ==========================================================
    # CONFIGURAÇÕES FINANCEIRAS E TAXAS
    # ==========================================================
    taxa_lixo = db.Column(db.Float, default=5.0)  # MZN fixos
    taxa_radio = db.Column(db.Float, default=3.0)  # MZN fixos
    iva_percent = db.Column(db.Float, default=16.0)  # Percentual
    
    # ==========================================================
    # CONFIGURAÇÕES DE NOTIFICAÇÃO - TELEGRAM
    # ==========================================================
    telegram_bot_token = db.Column(db.String(200), default='')
    telegram_chat_id = db.Column(db.String(50), default='')
    notify_telegram = db.Column(db.Boolean, default=False)
    
    # ==========================================================
    # CONFIGURAÇÕES DE NOTIFICAÇÃO - EMAIL
    # ==========================================================
    smtp_server = db.Column(db.String(100), default='smtp.gmail.com')
    smtp_port = db.Column(db.Integer, default=587)
    email_sender = db.Column(db.String(120), default='')
    email_password = db.Column(db.String(200), default='')
    email_notificacao = db.Column(db.String(120), default='admin@example.com')
    notify_email = db.Column(db.Boolean, default=True)
    email_frequency = db.Column(db.String(20), default='immediate')
    
    # ==========================================================
    # CONFIGURAÇÕES DE NOTIFICAÇÃO - BROWSER
    # ==========================================================
    notify_browser = db.Column(db.Boolean, default=True)
    
    # ==========================================================
    # CONFIGURAÇÕES DE ALERTAS ESPECÍFICOS
    # ==========================================================
    alert_saldo_baixo = db.Column(db.Boolean, default=True)
    alert_consumo_pico = db.Column(db.Boolean, default=True)
    alert_reles_desligados = db.Column(db.Boolean, default=True)
    alert_pzem_offline = db.Column(db.Boolean, default=True)
    alert_erro_sistema = db.Column(db.Boolean, default=True)
    saldo_baixo_limite = db.Column(db.Float, default=5.0)
    
# ==========================================================
# ROTAS DE CONFIGURAÇÃO DE NOTIFICAÇÕES
# ==========================================================

@app.route('/config/notificacoes', methods=['GET'])
@login_required
def get_notificacoes_config():
    """Obter configurações de notificação"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({
            # Telegram
            "notify_telegram": False,
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            
            # Email
            "notify_email": True,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "email_sender": "",
            "email_password": "",
            "email_notificacao": "",
            "email_frequency": "immediate",
            
            # Browser
            "notify_browser": True,
            
            # Limite de saldo baixo
            "saldo_baixo_limite": 5.0,
            
            # Alertas
            "alert_saldo_baixo": True,
            "alert_consumo_pico": True,
            "alert_reles_desligados": True,
            "alert_pzem_offline": True,
            "alert_erro_sistema": True
        })
    
    return jsonify({
        # Telegram
        "notify_telegram": config.notify_telegram,
        "telegram_bot_token": config.telegram_bot_token or "",
        "telegram_chat_id": config.telegram_chat_id or "",
        
        # Email
        "notify_email": config.notify_email,
        "smtp_server": config.smtp_server or "smtp.gmail.com",
        "smtp_port": config.smtp_port or 587,
        "email_sender": config.email_sender or "",
        "email_password": config.email_password or "",
        "email_notificacao": config.email_notificacao or "",
        "email_frequency": config.email_frequency or "immediate",
        
        # Browser
        "notify_browser": config.notify_browser,
        
        # Limite de saldo baixo
        "saldo_baixo_limite": config.saldo_baixo_limite or 5.0,
        
        # Alertas
        "alert_saldo_baixo": config.alert_saldo_baixo,
        "alert_consumo_pico": config.alert_consumo_pico,
        "alert_reles_desligados": config.alert_reles_desligados,
        "alert_pzem_offline": config.alert_pzem_offline,
        "alert_erro_sistema": config.alert_erro_sistema
    })

@app.route('/config/notificacoes', methods=['POST'])
@login_required
def save_notificacoes_config():
    """Salvar configurações de notificação"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    try:
        print(f"💾 Salvando configurações de notificação...")
        
        # Configurações do Telegram
        if 'telegram_bot_token' in data:
            config.telegram_bot_token = data['telegram_bot_token']
            print(f"   🤖 Token Telegram: {len(data['telegram_bot_token'])} caracteres")
        
        if 'telegram_chat_id' in data:
            config.telegram_chat_id = data['telegram_chat_id']
            print(f"   💬 Chat ID: {data['telegram_chat_id']}")
        
        if 'notify_telegram' in data:
            config.notify_telegram = bool(data['notify_telegram'])
            print(f"   📱 Notificar Telegram: {config.notify_telegram}")
        
        # Configurações de Email
        if 'smtp_server' in data:
            config.smtp_server = data['smtp_server'].strip() if data['smtp_server'] else 'smtp.gmail.com'
            print(f"   📧 SMTP Server: '{config.smtp_server}'")
        
        if 'smtp_port' in data:
            try:
                config.smtp_port = int(data['smtp_port']) if data['smtp_port'] else 587
            except (ValueError, TypeError):
                config.smtp_port = 587
            print(f"   🔌 SMTP Port: {config.smtp_port}")
        
        if 'email_sender' in data:
            config.email_sender = data['email_sender'].strip() if data['email_sender'] else ''
            print(f"   📨 Email Sender: '{config.email_sender}'")
        
        if 'email_password' in data:
            config.email_password = data['email_password'] if data['email_password'] else ''
            print(f"   🔐 Email Password: {'*' * len(data['email_password'])}")
        
        if 'email_notificacao' in data:
            config.email_notificacao = data['email_notificacao'].strip() if data['email_notificacao'] else ''
            print(f"   🎯 Email Notificação: '{config.email_notificacao}'")
        
        if 'notify_email' in data:
            config.notify_email = bool(data['notify_email'])
            print(f"   📧 Notificar Email: {config.notify_email}")
        
        if 'email_frequency' in data:
            config.email_frequency = data['email_frequency'] if data['email_frequency'] else 'immediate'
            print(f"   ⏰ Frequência Email: {config.email_frequency}")
        
        # Configurações do Browser
        if 'notify_browser' in data:
            config.notify_browser = bool(data['notify_browser'])
            print(f"   🔔 Notificar Browser: {config.notify_browser}")
        
        # Limite de saldo baixo
        if 'saldo_baixo_limite' in data:
            try:
                config.saldo_baixo_limite = float(data['saldo_baixo_limite'])
                print(f"   💰 Limite saldo baixo: {config.saldo_baixo_limite:.1f} kWh")
            except (ValueError, TypeError):
                config.saldo_baixo_limite = 5.0
        
        # Alertas específicos
        alertas = [
            'alert_saldo_baixo', 'alert_consumo_pico', 'alert_reles_desligados',
            'alert_pzem_offline', 'alert_erro_sistema'
        ]
        
        for alerta in alertas:
            if alerta in data:
                setattr(config, alerta, bool(data[alerta]))
                print(f"   ⚠️ {alerta}: {bool(data[alerta])}")

        db.session.commit()
        print("✅ Configurações salvas com sucesso!")
        return jsonify({"success": True, "message": "Configurações de notificação salvas com sucesso!"})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao salvar: {str(e)}")
        return jsonify({"success": False, "message": f"Erro ao salvar: {str(e)}"}), 500

@app.route('/config/notificacoes/testar', methods=['POST'])
@login_required
def testar_notificacao():
    """Testar notificações"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    tipo = data.get('tipo')
    config = Configuracao.query.first()
    
    try:
        if tipo == 'email':
            return testar_email(config)
        
        elif tipo == 'telegram':
            return testar_telegram(config)
        
        elif tipo == 'browser':
            return jsonify({"success": True, "message": "Notificação de browser configurada!"})
        
        else:
            return jsonify({"success": False, "message": "Tipo de notificação inválido"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao testar notificação: {str(e)}"}), 500

def testar_telegram(config):
    """Testar conexão com Telegram"""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return jsonify({"success": False, "message": "Token do bot ou Chat ID não configurado"})
    
    try:
        import requests
        
        # Testar se o bot token é válido
        bot_info_url = f"https://api.telegram.org/bot{config.telegram_bot_token}/getMe"
        bot_response = requests.get(bot_info_url, timeout=10)
        
        if not bot_response.json().get('ok'):
            return jsonify({"success": False, "message": "Token do bot inválido"})
        
        # Enviar mensagem de teste
        message_url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': config.telegram_chat_id,
            'text': '✅ Teste do Sistema de Energia\nEsta é uma mensagem de teste do seu sistema de monitoramento de energia.',
            'parse_mode': 'HTML'
        }
        
        response = requests.post(message_url, data=payload, timeout=10)
        
        if response.json().get('ok'):
            return jsonify({"success": True, "message": "Mensagem de teste enviada com sucesso para o Telegram!"})
        else:
            error = response.json().get('description', 'Erro desconhecido')
            return jsonify({"success": False, "message": f"Erro ao enviar mensagem: {error}"})
            
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "Timeout na conexão com Telegram"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro de conexão: {str(e)}"})

def testar_email(config):
    """Testar configuração de email"""
    print(f"🔍 Validando configurações de email...")
    print(f"📧 SMTP Server: '{config.smtp_server}'")
    print(f"🔌 SMTP Port: {config.smtp_port}")
    print(f"📨 Email Sender: '{config.email_sender}'")
    print(f"🔐 Email Password: {'*' * len(config.email_password) if config.email_password else 'VAZIO'}")
    print(f"🎯 Email Notificação: '{config.email_notificacao}'")
    
    # Validação mais flexível
    if not config.smtp_server or not config.smtp_server.strip():
        config.smtp_server = "smtp.gmail.com"
        print("⚠️  SMTP Server não configurado, usando padrão: smtp.gmail.com")
    
    if not config.smtp_port or config.smtp_port <= 0:
        config.smtp_port = 587
        print("⚠️  Porta SMTP inválida, usando padrão: 587")
    
    if not config.email_sender or not config.email_sender.strip():
        return jsonify({"success": False, "message": "Email de envio não configurado"})
    
    if not config.email_password or not config.email_password.strip():
        return jsonify({"success": False, "message": "Senha do email não configurada"})
    
    if not config.email_notificacao or not config.email_notificacao.strip():
        return jsonify({"success": False, "message": "Email para notificações não configurado"})
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Criar mensagem de teste
        msg = MIMEMultipart()
        msg['From'] = config.email_sender
        msg['To'] = config.email_notificacao
        msg['Subject'] = '✅ Teste do Sistema de Energia'
        
        body = f"""
        <h3>Teste do Sistema de Monitoramento de Energia</h3>
        <p>Esta é uma mensagem de teste para verificar a configuração do email.</p>
        <p><strong>Configuração testada:</strong></p>
        <ul>
            <li>Servidor: {config.smtp_server}:{config.smtp_port}</li>
            <li>Email de envio: {config.email_sender}</li>
            <li>Email de destino: {config.email_notificacao}</li>
        </ul>
        <p>Se você recebeu esta mensagem, o sistema de notificações por email está funcionando corretamente!</p>
        <hr>
        <small>Sistema de Automação Residencial - {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        print(f"🔄 Conectando ao servidor {config.smtp_server}:{config.smtp_port}...")
        
        # Conexão com tratamento de diferentes portas
        if config.smtp_port == 465:
            print("🔒 Usando SSL (porta 465)")
            server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=15)
        else:
            print("🔐 Usando TLS (porta 587)")
            server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=15)
            server.starttls()
        
        print(f"🔐 Efetuando login como {config.email_sender}...")
        server.login(config.email_sender, config.email_password)
        
        print(f"📤 Enviando email para {config.email_notificacao}...")
        text = msg.as_string()
        server.sendmail(config.email_sender, config.email_notificacao, text)
        server.quit()
        
        print(f"✅ Email de teste enviado com sucesso!")
        return jsonify({"success": True, "message": "Email de teste enviado com sucesso!"})
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Erro de autenticação: {str(e)}"
        print(f"❌ {error_msg}")
        
        if "gmail.com" in config.email_sender.lower():
            error_msg += "\n💡 Dica: Use uma SENHA DE APLICATIVO do Gmail, não a senha da conta."
            
        return jsonify({"success": False, "message": error_msg})
    
    except Exception as e:
        error_msg = f"Erro ao enviar email: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "message": error_msg})

# ==========================================================
# SERVIÇO DE NOTIFICAÇÕES - INTEGRAÇÃO COMPLETA
# ==========================================================

class ServicoNotificacoes:
    def __init__(self):
        self.ultima_verificacao = None
        self.alertas_enviados = set()
        self.ultimo_email_diario = None

    def verificar_todas_notificacoes(self):
        """Verifica todos os eventos e envia notificações se necessário"""
        try:
            config = Configuracao.query.first()
            if not config:
                return

            print("🔔 Verificando notificações...")

            # 1. SALDO BAIXO - COM LIMITE PERSONALIZADO
            if config.alert_saldo_baixo:
                self.verificar_saldo_baixo(config)

            # 2. CONSUMO EM PICO
            if config.alert_consumo_pico:
                self.verificar_consumo_pico(config)

            # 3. RELÉS DESLIGADOS
            if config.alert_reles_desligados:
                self.verificar_reles_desligados(config)

            # 4. PZEM OFFLINE
            if config.alert_pzem_offline:
                self.verificar_pzem_offline(config)

            # 5. ERROS NO SISTEMA
            if config.alert_erro_sistema:
                self.verificar_erros_sistema(config)

            # Limpar alertas antigos
            self.limpar_alertas_antigos()

        except Exception as e:
            print(f"❌ Erro na verificação de notificações: {e}")

    def verificar_saldo_baixo(self, config):
        """Verifica se o saldo está baixo usando o limite personalizado"""
        limite_saldo_baixo = config.saldo_baixo_limite or 5.0  # kWh
        
        if config.saldo_kwh <= limite_saldo_baixo:
            alerta_id = f"saldo_baixo_{datetime.now().strftime('%Y%m%d%H')}"
            
            if alerta_id not in self.alertas_enviados:
                mensagem = (
                    f"⚠️ **SALDO BAIXO** ⚠️\n"
                    f"Saldo atual: {config.saldo_kwh:.2f} kWh\n"
                    f"Valor: {config.saldo_kwh * config.preco_kwh:.2f} MZN\n"
                    f"Limite configurado: {limite_saldo_baixo} kWh\n"
                    f"⏰ {datetime.now().strftime('%H:%M')}"
                )
                
                self.enviar_notificacao('saldo_baixo', mensagem, config)
                self.alertas_enviados.add(alerta_id)
                print(f"🔔 Alerta de saldo baixo: {config.saldo_kwh:.2f} kWh ≤ {limite_saldo_baixo} kWh")

    def verificar_consumo_pico(self, config):
        """Verifica se o consumo está em pico (acima de 80% do limite)"""
        # Obter dados dos PZEMs (ajuste conforme sua estrutura de dados)
        consumo_total = 0
        try:
            # Exemplo - ajuste para seus dados reais
            from app import dados_pzem  # ou importe de onde vem seus dados
            consumo_total = dados_pzem.get('pzem1', {}).get('power', 0) + dados_pzem.get('pzem2', {}).get('power', 0)
        except:
            # Fallback caso não consiga obter os dados
            consumo_total = 0
        
        limite_total = config.limite_pzem1 + config.limite_pzem2
        limite_pico = limite_total * 0.8  # 80% do limite total
        
        if consumo_total >= limite_pico:
            alerta_id = f"consumo_pico_{datetime.now().strftime('%Y%m%d%H')}"
            
            if alerta_id not in self.alertas_enviados:
                percentual = (consumo_total / limite_total) * 100
                mensagem = (
                    f"⚡ **CONSUMO EM PICO** ⚡\n"
                    f"Consumo atual: {consumo_total:.0f}W\n"
                    f"Limite do sistema: {limite_total:.0f}W\n"
                    f"Utilização: {percentual:.1f}%\n"
                    f"⏰ {datetime.now().strftime('%H:%M')}"
                )
                
                self.enviar_notificacao('consumo_pico', mensagem, config)
                self.alertas_enviados.add(alerta_id)
                print(f"🔔 Alerta de consumo em pico: {consumo_total:.0f}W")

    def verificar_reles_desligados(self, config):
        """Verifica se relés foram desligados automaticamente recentemente"""
        try:
            from app import comandos_pendentes, dados_lock
            
            with dados_lock:
                comandos_desligar = [cmd for cmd in comandos_pendentes if cmd.endswith('_OFF')]
            
            if comandos_desligar:
                for comando in comandos_desligar:
                    alerta_id = f"rele_desligado_{comando}_{datetime.now().strftime('%Y%m%d%H')}"
                    
                    if alerta_id not in self.alertas_enviados:
                        rele_id = comando.replace('RELE', '').replace('_OFF', '')
                        mensagem = (
                            f"🔌 **RELÉ DESLIGADO** 🔌\n"
                            f"Relé {rele_id} foi desligado automaticamente\n"
                            f"Motivo: Saldo baixo ou limite atingido\n"
                            f"Saldo atual: {config.saldo_kwh:.2f} kWh\n"
                            f"⏰ {datetime.now().strftime('%H:%M')}"
                        )
                        
                        self.enviar_notificacao('reles_desligados', mensagem, config)
                        self.alertas_enviados.add(alerta_id)
                        print(f"🔔 Alerta de relé desligado: {comando}")
        except Exception as e:
            print(f"❌ Erro ao verificar relés desligados: {e}")

    def verificar_pzem_offline(self, config):
        """Verifica se algum PZEM está offline"""
        try:
            from app import dados_pzem
            
            agora = datetime.now(timezone.utc)
            
            for pzem_id in [1, 2]:
                pzem_key = f'pzem{pzem_id}'
                ultima_atualizacao = dados_pzem.get(pzem_key, {}).get('ultima_atualizacao')
                
                if ultima_atualizacao:
                    tempo_desconectado = (agora - ultima_atualizacao).total_seconds()
                    
                    # Considera offline se não atualizou há mais de 2 minutos
                    if tempo_desconectado > 120:  # 2 minutos
                        alerta_id = f"pzem_offline_{pzem_id}_{datetime.now().strftime('%Y%m%d%H')}"
                        
                        if alerta_id not in self.alertas_enviados:
                            mensagem = (
                                f"❌ **PZEM OFFLINE** ❌\n"
                                f"PZEM {pzem_id} desconectado\n"
                                f"Tempo offline: {tempo_desconectado/60:.1f} minutos\n"
                                f"Última atualização: {ultima_atualizacao.strftime('%H:%M')}\n"
                                f"⏰ {datetime.now().strftime('%H:%M')}"
                            )
                            
                            self.enviar_notificacao('pzem_offline', mensagem, config)
                            self.alertas_enviados.add(alerta_id)
                            print(f"🔔 Alerta de PZEM offline: {pzem_key}")
        except Exception as e:
            print(f"❌ Erro ao verificar PZEM offline: {e}")

    def verificar_erros_sistema(self, config):
        """Monitora erros no sistema"""
        # Esta função pode ser expandida para monitorar logs específicos
        # Por enquanto, é um placeholder para futuras implementações
        pass

    def enviar_notificacao(self, tipo, mensagem, config):
        """Envia notificação por todos os canais configurados"""
        try:
            # Telegram
            if config.notify_telegram and config.telegram_bot_token and config.telegram_chat_id:
                self.enviar_telegram(mensagem, config)
            
            # Email (apenas para alertas críticos)
            if config.notify_email and tipo in ['saldo_baixo', 'pzem_offline', 'erro_sistema']:
                self.enviar_email(tipo, mensagem, config)
            
            # Browser (sempre que possível)
            if config.notify_browser:
                self.enviar_browser(tipo, mensagem)
                
        except Exception as e:
            print(f"❌ Erro ao enviar notificação: {e}")

    def enviar_telegram(self, mensagem, config):
        """Envia mensagem via Telegram (compatível Railway)"""
        try:
            import requests

            url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"

            payload = {
                'chat_id': str(config.telegram_chat_id).strip(),
                'text': mensagem,
                'parse_mode': 'HTML'
            }

            # ⚠️ Railway precisa JSON + cabeçalho
            response = requests.post(
                url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )

            if response.json().get('ok'):
                print("✅ Notificação Telegram enviada")
            else:
                print(f"❌ Erro Telegram:", response.json())

        except Exception as e:
            print(f"❌ Erro ao enviar Telegram: {e}")


    def enviar_email(self, tipo, mensagem, config):
            """Envia email de notificação"""
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                # Configurar mensagem
                msg = MIMEMultipart()
                msg['From'] = config.email_sender
                msg['To'] = config.email_notificacao
                msg['Subject'] = f"🔔 Alerta do Sistema - {tipo.upper()}"
                
                # Corpo do email
                body = f"""
                <h2>Alerta do Sistema de Energia</h2>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                    {mensagem.replace('\n', '<br>')}
                </div>
                <br>
                <small>Sistema de Automação Residencial - {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
                """
                
                msg.attach(MIMEText(body, 'html'))
                
                # Enviar email
                if config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=15)
                else:
                    server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=15)
                    server.starttls()
                
                server.login(config.email_sender, config.email_password)
                server.sendmail(config.email_sender, config.email_notificacao, msg.as_string())
                server.quit()
                
                print("✅ Notificação Email enviada")
                
            except Exception as e:
                print(f"❌ Erro ao enviar Email: {e}")

    def enviar_browser(self, tipo, mensagem):
            """Envia notificação no navegador (será capturada pelo JavaScript)"""
            # Esta notificação será processada pelo frontend
            print(f"🔔 Notificação Browser: {tipo} - {mensagem}")

    def limpar_alertas_antigos(self):
            """Remove alertas antigos do conjunto para evitar duplicação"""
            agora = datetime.now()
            alertas_para_remover = []
            
            for alerta_id in self.alertas_enviados:
                # Remove alertas com mais de 24 horas
                if agora.strftime('%Y%m%d') not in alerta_id:
                    alertas_para_remover.append(alerta_id)
            
            for alerta_id in alertas_para_remover:
                self.alertas_enviados.remove(alerta_id)

# ==========================================================
# INICIALIZAÇÃO DO SERVIÇO
# ==========================================================
servico_notificacoes = ServicoNotificacoes()

# ==========================================================
# ROTAS ADICIONAIS PARA DEBUG
# ==========================================================

@app.route('/config/notificacoes/debug-detalhado', methods=['GET'])
@login_required
def debug_notificacoes_detalhado():
    """Debug detalhado das configurações de notificação"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({"error": "Configuração não encontrada"}), 404
    
    return jsonify({
        "all_config_fields": {
            "smtp_server": {
                "value": config.smtp_server,
                "type": type(config.smtp_server).__name__,
                "is_empty": not bool(config.smtp_server and config.smtp_server.strip())
            },
            "smtp_port": {
                "value": config.smtp_port,
                "type": type(config.smtp_port).__name__
            },
            "email_sender": {
                "value": config.email_sender,
                "type": type(config.email_sender).__name__,
                "is_empty": not bool(config.email_sender and config.email_sender.strip())
            },
            "email_password": {
                "value": "***" if config.email_password else "",
                "length": len(config.email_password) if config.email_password else 0,
                "is_empty": not bool(config.email_password and config.email_password.strip())
            },
            "email_notificacao": {
                "value": config.email_notificacao,
                "type": type(config.email_notificacao).__name__,
                "is_empty": not bool(config.email_notificacao and config.email_notificacao.strip())
            },
            "telegram_bot_token": {
                "value": "***" if config.telegram_bot_token else "",
                "length": len(config.telegram_bot_token) if config.telegram_bot_token else 0,
                "is_empty": not bool(config.telegram_bot_token and config.telegram_bot_token.strip())
            },
            "telegram_chat_id": {
                "value": config.telegram_chat_id,
                "type": type(config.telegram_chat_id).__name__,
                "is_empty": not bool(config.telegram_chat_id and config.telegram_chat_id.strip())
            }
        }
    })

@app.route('/config/notificacoes/status', methods=['GET'])
@login_required
def status_notificacoes():
    """Status atual do serviço de notificações"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({"error": "Configuração não encontrada"}), 404
    
    return jsonify({
        "servico_ativos": {
            "telegram": config.notify_telegram and bool(config.telegram_bot_token and config.telegram_chat_id),
            "email": config.notify_email and bool(config.email_sender and config.email_password and config.email_notificacao),
            "browser": config.notify_browser
        },
        "alertas_ativos": {
            "saldo_baixo": config.alert_saldo_baixo,
            "consumo_pico": config.alert_consumo_pico,
            "reles_desligados": config.alert_reles_desligados,
            "pzem_offline": config.alert_pzem_offline,
            "erro_sistema": config.alert_erro_sistema
        },
        "limite_saldo_baixo": config.saldo_baixo_limite,
        "ultima_verificacao": servico_notificacoes.ultima_verificacao.isoformat() if servico_notificacoes.ultima_verificacao else None,
        "alertas_pendentes": len(servico_notificacoes.alertas_enviados)
    })


    # ==========================================================
    # MÉTODOS DA CLASSE
    # ==========================================================
    
    def to_dict(self):
        """Converter configurações para dicionário"""
        return {
            # Limites e consumo
            'limite_pzem1': self.limite_pzem1,
            'limite_pzem2': self.limite_pzem2,
            'preco_kwh': self.preco_kwh,
            'saldo_kwh': self.saldo_kwh,
            'prioridade_minima_emergencia': self.prioridade_minima_emergencia,
            
            # Configurações financeiras
            'taxa_lixo': self.taxa_lixo,
            'taxa_radio': self.taxa_radio,
            'iva_percent': self.iva_percent,
            
            # Telegram
            'telegram_bot_token': self.telegram_bot_token,
            'telegram_chat_id': self.telegram_chat_id,
            'notify_telegram': self.notify_telegram,
            
            # Email
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'email_sender': self.email_sender,
            'email_password': self.email_password,
            'email_notificacao': self.email_notificacao,
            'notify_email': self.notify_email,
            'email_frequency': self.email_frequency,
            
            # Browser
            'notify_browser': self.notify_browser,
            
            # Alertas
            'alert_saldo_baixo': self.alert_saldo_baixo,
            'alert_consumo_pico': self.alert_consumo_pico,
            'alert_reles_desligados': self.alert_reles_desligados,
            'alert_pzem_offline': self.alert_pzem_offline,
            'alert_erro_sistema': self.alert_erro_sistema
        }

class Recarga(db.Model):
    __tablename__ = 'recargas'
    id = db.Column(db.Integer, primary_key=True)
    valor_mzn = db.Column(db.Float, nullable=False)
    taxa_lixo = db.Column(db.Float, default=0.0)
    taxa_radio = db.Column(db.Float, default=0.0)
    iva_percent = db.Column(db.Float, default=0.0)
    preco_kwh = db.Column(db.Float, nullable=False)
    kwh_creditados = db.Column(db.Float, default=0.0)
    saldo_anterior = db.Column(db.Float, default=0.0)
    saldo_atual = db.Column(db.Float, default=0.0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "valor_mzn": self.valor_mzn,
            "taxa_lixo": self.taxa_lixo,
            "taxa_radio": self.taxa_radio,
            "iva_percent": self.iva_percent,
            "preco_kwh": self.preco_kwh,
            "kwh_creditados": self.kwh_creditados,
            "saldo_anterior": self.saldo_anterior,
            "saldo_atual": self.saldo_atual,
            "criado_em": self.criado_em.strftime("%Y-%m-%d %H:%M:%S")
        }


# ==========================================================
#                    DADOS LDR   
# ==========================================================
@app.route("/api/ldr", methods=["POST"])
def receber_ldr():
    global ULTIMO_LDR

    data = request.get_json()

    if not data or "api_key" not in data or data["api_key"] not in API_KEYS:
        return {"error": "Unauthorized"}, 401

    ULTIMO_LDR["valorLuz"] = data.get("valorLuz", 0)
    ULTIMO_LDR["R1"] = data.get("R1", 0)

    print(f"[LDR] valorLuz={ULTIMO_LDR['valorLuz']} | R1={ULTIMO_LDR['R1']}")

    return {"success": True}

@app.route("/api/get_ldr", methods=["GET"])
def get_ldr():
    return {
        "success": True,
        "valorLuz": ULTIMO_LDR["valorLuz"],
        "R1": ULTIMO_LDR["R1"]
    }

# ==========================================================
                   # RELATORIOS
# ==========================================================
@app.route('/api/relatorio', methods=['POST'])
@login_required
def gerar_relatorio():
    """Gera relatórios consolidados do sistema"""
    data = request.get_json()
    
    # Validação básica
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400
    
    tipo = data.get("type")
    periodo = data.get("period")
    pzem = data.get("pzem", "all")
    start_date = data.get("startDate")
    end_date = data.get("endDate")

    # ============================
    # 1) Determinar intervalo de datas
    # ============================
    today = datetime.utcnow().date()

    try:
        if periodo == "today":
            dt_start = today
            dt_end = today
        elif periodo == "yesterday":
            dt_start = today - timedelta(days=1)
            dt_end = dt_start
        elif periodo == "week":
            dt_start = today - timedelta(days=today.weekday())  # Segunda-feira
            dt_end = today
        elif periodo == "month":
            dt_start = today.replace(day=1)
            dt_end = today
        elif periodo == "custom":
            if not start_date or not end_date:
                return jsonify({"success": False, "message": "Datas customizadas requerem startDate e endDate"}), 400
            dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            dt_end = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Validar intervalo (máximo 1 ano)
            if (dt_end - dt_start).days > 365:
                return jsonify({"success": False, "message": "Intervalo máximo é de 365 dias"}), 400
        else:
            return jsonify({"success": False, "message": "Período inválido"}), 400
    except ValueError as e:
        return jsonify({"success": False, "message": f"Formato de data inválido: {str(e)}"}), 400

    # ============================
    # 2) Consulta base com filtros
    # ============================
    base_query = EnergyData.query.filter(
        func.date(EnergyData.timestamp) >= dt_start,
        func.date(EnergyData.timestamp) <= dt_end
    )

    if pzem != "all":
        try:
            base_query = base_query.filter(EnergyData.pzem_id == int(pzem))
        except ValueError:
            return jsonify({"success": False, "message": "PZEM ID inválido"}), 400

    dados = []
    cfg = Configuracao.query.first()
    if not cfg:
        return jsonify({"success": False, "message": "Configuração do sistema não encontrada"}), 500
    
    if tipo == "recargas":
        try:
            # Para recargas, ignoramos o filtro de PZEM
            recargas = Recarga.query.filter(
                func.date(Recarga.criado_em) >= dt_start,
                func.date(Recarga.criado_em) <= dt_end
            ).order_by(Recarga.criado_em.desc()).all()

            for recarga in recargas:
                dados.append({
                    "criado_em": recarga.criado_em.strftime("%Y-%m-%d %H:%M:%S"),
                    "valor_mzn": recarga.valor_mzn,
                    "kwh_creditados": recarga.kwh_creditados,
                    "taxa_lixo": recarga.taxa_lixo,
                    "taxa_radio": recarga.taxa_radio,
                    "iva_percent": recarga.iva_percent,
                    "preco_kwh": recarga.preco_kwh,
                    "saldo_anterior": recarga.saldo_anterior,
                    "saldo_atual": recarga.saldo_atual
                })

            return jsonify({
                "success": True, 
                "dados": dados,
                "metadata": {
                    "periodo": f"{dt_start} a {dt_end}",
                    "total_registros": len(dados),
                    "tipo": "historico_recargas",
                    "pzem": "N/A"  # Recargas não dependem de PZEM
                }
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Erro ao gerar relatório de recargas: {str(e)}"}), 500

    # ============================
    # 3) Relatório de Consumo de Energia
    # ============================
    if tipo == "consumo":
        try:
            rows = db.session.query(
                func.date(EnergyData.timestamp).label("data"),
                func.sum(EnergyData.energy).label("energia_total")
            ).filter(
                func.date(EnergyData.timestamp) >= dt_start,
                func.date(EnergyData.timestamp) <= dt_end
            )
            
            if pzem != "all":
                rows = rows.filter(EnergyData.pzem_id == int(pzem))
                
            rows = rows.group_by(func.date(EnergyData.timestamp)).all()

            for data, energia in rows:
                custo = energia * cfg.preco_kwh
                dados.append({
                    "data": data.strftime("%Y-%m-%d"),
                    "energia": round(float(energia), 3),
                    "custo": round(float(custo), 2)
                })
            
            return jsonify({
                "success": True, 
                "dados": dados,
                "metadata": {
                    "periodo": f"{dt_start} a {dt_end}",
                    "total_registros": len(dados),
                    "pzem": pzem,
                    "tipo": "consumo"
                }
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Erro ao gerar relatório de consumo: {str(e)}"}), 500

    # ============================
    # 4) Relatório de Picos de Consumo
    # ============================
    elif tipo == "picos":
        try:
            rows = db.session.query(
                func.date(EnergyData.timestamp).label("data"),
                func.max(EnergyData.power).label("pico_potencia"),
                func.min(EnergyData.timestamp).label("primeira_ocorrencia")
            ).filter(
                func.date(EnergyData.timestamp) >= dt_start,
                func.date(EnergyData.timestamp) <= dt_end
            )
            
            if pzem != "all":
                rows = rows.filter(EnergyData.pzem_id == int(pzem))
                
            rows = rows.group_by(func.date(EnergyData.timestamp)).all()

            for data, pico, timestamp in rows:
                dados.append({
                    "data": data.strftime("%Y-%m-%d"),
                    "pico": round(float(pico), 1),
                    "hora": timestamp.time().strftime("%H:%M") if timestamp else "--:--"
                })

            return jsonify({
                "success": True, 
                "dados": dados,
                "metadata": {
                    "periodo": f"{dt_start} a {dt_end}",
                    "total_registros": len(dados),
                    "pzem": pzem,
                    "tipo": "picos"
                }
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Erro ao gerar relatório de picos: {str(e)}"}), 500

# ==========================================================
# 5) Relatório de Desempenho por Relé - CORRIGIDA
# ==========================================================
    elif tipo == "reles":
        try:
            reles = Rele.query.all()
            if not reles:
                return jsonify({"success": False, "message": "Nenhum relé configurado"}), 404

            dados = []
            for rele in reles:
                # Calcular consumo médio - CORREÇÃO: garantir que não seja None
                consumo_medio_result = db.session.query(func.avg(EnergyData.power)).filter(
                    EnergyData.pzem_id == rele.pzem_id,
                    func.date(EnergyData.timestamp) >= dt_start,
                    func.date(EnergyData.timestamp) <= dt_end
                ).scalar()
                
                consumo_medio = float(consumo_medio_result) if consumo_medio_result is not None else 0.0

                # Contar mudanças de estado no período
                mudancas_count = ReleLog.query.filter(
                    ReleLog.rele_id == rele.id,
                    func.date(ReleLog.timestamp) >= dt_start,
                    func.date(ReleLog.timestamp) <= dt_end
                ).count()

                # Calcular dias do período
                dias_periodo = (dt_end - dt_start).days + 1
                
                # 🔥 CORREÇÃO: Garantir que todos os campos tenham valores padrão
                dados.append({
                    "nome": rele.nome or "Sem nome",
                    "pzem_id": rele.pzem_id or 1,
                    "consumo_medio": round(consumo_medio, 2),
                    "estado": "LIGADO" if rele.estado else "DESLIGADO",
                    "modo": "Automático" if rele.modo_automatico else "Manual",
                    "prioridade": rele.prioridade or 3,
                    "limite_individual": float(rele.limite_individual) if rele.limite_individual else 5.0,
                    "tempo_ligado": "0.0h",  # Valor padrão
                    "tempo_desligado": "0.0h",  # Valor padrão
                    "ciclos": mudancas_count,
                    "eficiencia_tempo": "0%",  # Valor padrão
                    "mudancas_estado": mudancas_count,
                    "periodo_analisado": f"{dias_periodo} dias"
                })

            return jsonify({
                "success": True, 
                "dados": dados,
                "metadata": {
                    "periodo": f"{dt_start} a {dt_end}",
                    "total_reles": len(reles),
                    "tipo": "desempenho_reles",
                    "dias_analisados": dias_periodo
                }
            })
        except Exception as e:
            print(f"❌ Erro no relatório de relés: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            return jsonify({"success": False, "message": f"Erro ao gerar relatório de relés: {str(e)}"}), 500  
# ============================================================
# 6) Relatório de Análise de Custos
# # ==========================================================
    elif tipo == "custo":
        try:
            cfg = Configuracao.query.first()
            if not cfg:
                return jsonify({"success": False, "message": "Configuração do sistema não encontrada"}), 500
            
            # 1️⃣ DADOS DE CONSUMO
            rows = db.session.query(
                func.date(EnergyData.timestamp).label("data"),
                func.sum(EnergyData.energy).label("energia_total")
            ).filter(
                func.date(EnergyData.timestamp) >= dt_start,
                func.date(EnergyData.timestamp) <= dt_end
            )
            
            if pzem != "all":
                rows = rows.filter(EnergyData.pzem_id == int(pzem))
                
            rows = rows.group_by(func.date(EnergyData.timestamp)).all()

            # 2️⃣ DADOS DE RECARGAS
            recargas_periodo = db.session.query(
                func.sum(Recarga.valor_mzn).label("total_recargas")
            ).filter(
                func.date(Recarga.criado_em) >= dt_start,
                func.date(Recarga.criado_em) <= dt_end
            ).scalar() or 0

            # 3️⃣ DADOS PARA MÉTRICAS AVANÇADAS
            # Consumo atual para previsões
            consumo_atual_w = dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power']
            consumo_atual_kw = consumo_atual_w / 1000
            saldo_atual_kwh = cfg.saldo_kwh
            
            # Dados para análise comparativa
            periodo_anterior_start = dt_start - (dt_end - dt_start) - timedelta(days=1)
            periodo_anterior_end = dt_start - timedelta(days=1)
            
            consumo_periodo_anterior = db.session.query(
                func.sum(EnergyData.energy)
            ).filter(
                func.date(EnergyData.timestamp) >= periodo_anterior_start,
                func.date(EnergyData.timestamp) <= periodo_anterior_end
            ).scalar() or 0

            # 4️⃣ PROCESSAR DADOS DIÁRIOS
            custo_total = 0
            energia_total = 0
            dias_com_consumo = len(rows)

            dados = []  # Resetar dados para este relatório

            for data, energia in rows:
                custo_dia = energia * cfg.preco_kwh
                custo_total += custo_dia
                energia_total += energia
                
                dados.append({
                    "data": data.strftime("%Y-%m-%d"),
                    "energia": round(float(energia), 3),
                    "custo_dia": round(float(custo_dia), 2)
                })

            # 5️⃣ CÁLCULO DAS MÉTRICAS PROFISSIONAIS
            # Métricas básicas
            custo_medio_diario = custo_total / max(dias_com_consumo, 1)
            saldo_liquido = recargas_periodo - custo_total
            eficiencia_financeira = custo_total / max(energia_total, 1) if energia_total > 0 else 0
            
            # Previsão de duração do saldo
            if consumo_atual_kw > 0:
                horas_restantes = saldo_atual_kwh / consumo_atual_kw
                dias_restantes = horas_restantes / 24
                previsao_termino = datetime.now() + timedelta(hours=horas_restantes)
                previsao_str = previsao_termino.strftime('%d/%m %H:%M')
            else:
                dias_restantes = 0
                previsao_str = "Indeterminado"
            
            # Análise comparativa
            variacao_consumo = 0
            if consumo_periodo_anterior > 0:
                variacao_consumo = ((energia_total - consumo_periodo_anterior) / consumo_periodo_anterior * 100)
            
            # Análise de eficiência
            horas_pico = db.session.query(
                func.count(EnergyData.id)
            ).filter(
                EnergyData.power > (cfg.limite_pzem1 * 0.7),  # 70% do limite como pico
                func.date(EnergyData.timestamp) >= dt_start,
                func.date(EnergyData.timestamp) <= dt_end
            ).scalar() or 0

            total_registros = db.session.query(
                func.count(EnergyData.id)
            ).filter(
                func.date(EnergyData.timestamp) >= dt_start,
                func.date(EnergyData.timestamp) <= dt_end
            ).scalar() or 1

            percentual_horas_pico = (horas_pico / total_registros) * 100
            
            # Score de eficiência (0-100)
            score_eficiencia = max(0, min(100, 100 - (
                (min(percentual_horas_pico, 50) * 0.4) + 
                (max(0, min(variacao_consumo, 50)) * 0.3) + 
                (max(0, min((eficiencia_financeira - cfg.preco_kwh) / cfg.preco_kwh * 100, 50)) * 0.3)
            )))

            # Categoria de desempenho
            if score_eficiencia >= 80:
                categoria = "🏆 Excelente"
                cor_categoria = "success"
            elif score_eficiencia >= 60:
                categoria = "✅ Bom"
                cor_categoria = "info"
            elif score_eficiencia >= 40:
                categoria = "⚠️ Regular"
                cor_categoria = "warning"
            else:
                categoria = "🔴 Crítico"
                cor_categoria = "danger"

            # Projeções futuras
            dias_no_mes = 30
            if dias_com_consumo > 0:
                projecao_mensal_consumo = (energia_total / dias_com_consumo) * dias_no_mes
                projecao_mensal_custo = projecao_mensal_consumo * cfg.preco_kwh
                economia_potencial = projecao_mensal_custo * 0.12  # 12% de economia potencial
            else:
                projecao_mensal_consumo = 0
                projecao_mensal_custo = 0
                economia_potencial = 0

            # 6️⃣ ADICIONAR LINHAS DE RESUMO E MÉTRICAS
            # Separador
            dados.append({
                "data": "--- RESUMO DO PERÍODO ---",
                "energia": "-",
                "custo_dia": "-",
                "tipo": "separador"
            })
            
            # Dados principais
            dados.append({
                "data": "📊 TOTAL CONSUMO",
                "energia": round(float(energia_total), 3),
                "custo_dia": round(float(custo_total), 2),
                "tipo": "total_consumo"
            })

            dados.append({
                "data": "💰 TOTAL RECARGAS",
                "energia": "-",
                "custo_dia": round(float(recargas_periodo), 2),
                "tipo": "total_recargas"
            })

            dados.append({
                "data": "💹 SALDO LÍQUIDO" if saldo_liquido >= 0 else "🔻 SALDO LÍQUIDO",
                "energia": "-", 
                "custo_dia": round(float(saldo_liquido), 2),
                "tipo": "saldo_liquido"
            })
            
            # Separador de métricas
            dados.append({
                "data": "--- MÉTRICAS AVANÇADAS ---",
                "energia": "-",
                "custo_dia": "-",
                "tipo": "separador"
            })
            
            # Métricas básicas
            dados.append({
                "data": "📅 Custo Médio Diário",
                "energia": "-",
                "custo_dia": round(float(custo_medio_diario), 2),
                "tipo": "metrica"
            })
            
            dados.append({
                "data": "⚡ Custo por kWh",
                "energia": "-",
                "custo_dia": f"{round(float(eficiencia_financeira), 3)} MZN",
                "tipo": "metrica"
            })
            
            # Análise comparativa
            dados.append({
                "data": "📈 Variação Consumo" if variacao_consumo >= 0 else "📉 Variação Consumo",
                "energia": f"{abs(variacao_consumo):.1f}%",
                "custo_dia": "Aumento" if variacao_consumo >= 0 else "Redução",
                "tipo": "metrica"
            })
            
            # Eficiência
            dados.append({
                "data": "⏰ Horas em Pico",
                "energia": f"{percentual_horas_pico:.1f}%",
                "custo_dia": ">70% limite",
                "tipo": "metrica"
            })
            
            # Score
            dados.append({
                "data": "🎯 Score de Eficiência",
                "energia": categoria,
                "custo_dia": f"{score_eficiencia:.0f}/100",
                "tipo": "score"
            })
            
            # Previsões
            dados.append({
                "data": "🔮 Previsão Saldo Actual",
                "energia": f"{dias_restantes:.1f} dias",
                "custo_dia": previsao_str,
                "tipo": "previsao"
            })
            
            dados.append({
                "data": "📅 Projeção Mensal",
                "energia": f"{projecao_mensal_consumo:.1f} kWh",
                "custo_dia": f"{projecao_mensal_custo:.2f} MZN",
                "tipo": "projecao"
            })
            
            # Estado atual
            dados.append({
                "data": "🔋 Saldo Actual",
                "energia": f"{saldo_atual_kwh:.2f} kWh",
                "custo_dia": f"{(saldo_atual_kwh * cfg.preco_kwh):.2f} MZN",
                "tipo": "saldo_atual"
            })
            
            dados.append({
                "data": "⚡ Consumo Actual",
                "energia": f"{consumo_atual_kw:.2f} kW",
                "custo_dia": f"{(consumo_atual_kw * cfg.preco_kwh):.2f} MZN/h",
                "tipo": "consumo_atual"
            })
            
            # Economia potencial
            dados.append({
                "data": "💡 Economia Potencial",
                "energia": "-",
                "custo_dia": f"{economia_potencial:.2f} MZN/mês",
                "tipo": "economia"
            })

            return jsonify({
                "success": True, 
                "dados": dados,
                "metadata": {
                    "periodo": f"{dt_start} a {dt_end}",
                    "total_dias": dias_com_consumo,
                    "energia_total": round(energia_total, 3),
                    "custo_total": round(custo_total, 2),
                    "recargas_total": round(recargas_periodo, 2),
                    "saldo_liquido": round(saldo_liquido, 2),
                    "preco_kwh": cfg.preco_kwh,
                    "pzem": pzem,
                    "tipo": "analise_custos",
                    # MÉTRICAS AVANÇADAS
                    "metricas": {
                        "custo_medio_diario": round(custo_medio_diario, 2),
                        "eficiencia_financeira": round(eficiencia_financeira, 3),
                        "dias_restantes": round(dias_restantes, 1),
                        "previsao_termino": previsao_str,
                        "saldo_atual_kwh": round(saldo_atual_kwh, 2),
                        "saldo_atual_mzn": round(saldo_atual_kwh * cfg.preco_kwh, 2),
                        "consumo_atual_kw": round(consumo_atual_kw, 2),
                        "variacao_consumo": round(variacao_consumo, 1),
                        "percentual_horas_pico": round(percentual_horas_pico, 1),
                        "score_eficiencia": round(score_eficiencia, 0),
                        "categoria_eficiencia": categoria,
                        "cor_categoria": cor_categoria,
                        "projecao_mensal_custo": round(projecao_mensal_custo, 2),
                        "economia_potencial": round(economia_potencial, 2)
                    }
                }
            })
        except Exception as e:
            print(f"❌ Erro na análise de custos: {e}")
            return jsonify({"success": False, "message": f"Erro ao gerar relatório de custos: {str(e)}"}), 500

@app.route('/api/reles/<int:rele_id>/logs', methods=['GET'])
@login_required
def obter_logs_rele(rele_id):
    """Obter logs detalhados de um relé"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    logs = ReleLog.query.filter_by(rele_id=rele_id)\
                       .order_by(ReleLog.timestamp.desc())\
                       .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "success": True,
        "logs": [log.to_dict() for log in logs.items],
        "total": logs.total,
        "pages": logs.pages,
        "current_page": page
    })

def registrar_log_rele(rele_id, estado_anterior, estado_novo, motivo, modo_operacao=None):
    """Registra uma mudança de estado do relé no log"""
    try:
        config = Configuracao.query.first()
        saldo_atual = config.saldo_kwh if config else 0
        
        log = ReleLog(
            rele_id=rele_id,
            estado_anterior=estado_anterior,
            estado_novo=estado_novo,
            motivo=motivo,
            modo_operacao=modo_operacao,
            saldo_kwh=saldo_atual
        )
        
        db.session.add(log)
        db.session.commit()
        print(f"📝 Log relé {rele_id}: {estado_anterior} → {estado_novo} | Motivo: {motivo}")
        
    except Exception as e:
        print(f"❌ Erro ao registrar log do relé: {e}")
        db.session.rollback()
# ==========================================================
                   # NOTIFICACOES
# ==========================================================
@app.route('/config/notificacoes', methods=['GET'])
@login_required
def get_notificacoes_config():
    """Obter configurações de notificação"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({
            # Telegram
            "notify_telegram": False,
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            
            # Email
            "notify_email": True,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "email_sender": "",
            "email_password": "",
            "email_notificacao": "",
            "email_frequency": "immediate",
            
            # Browser
            "notify_browser": True,
            
            # 🔥 NOVO CAMPO: Limite de saldo baixo
            "saldo_baixo_limite": 5.0,
            
            # Alertas
            "alert_saldo_baixo": True,
            "alert_consumo_pico": True,
            "alert_reles_desligados": True,
            "alert_pzem_offline": True,
            "alert_erro_sistema": True
        })
    
    return jsonify({
        # Telegram
        "notify_telegram": config.notify_telegram,
        "telegram_bot_token": config.telegram_bot_token or "",
        "telegram_chat_id": config.telegram_chat_id or "",
        
        # Email
        "notify_email": config.notify_email,
        "smtp_server": config.smtp_server or "smtp.gmail.com",
        "smtp_port": config.smtp_port or 587,
        "email_sender": config.email_sender or "",
        "email_password": config.email_password or "",
        "email_notificacao": config.email_notificacao or "",
        "email_frequency": config.email_frequency or "immediate",
        
        # Browser
        "notify_browser": config.notify_browser,
        
        # 🔥 NOVO CAMPO: Limite de saldo baixo
        "saldo_baixo_limite": config.saldo_baixo_limite or 5.0,
        
        # Alertas
        "alert_saldo_baixo": config.alert_saldo_baixo,
        "alert_consumo_pico": config.alert_consumo_pico,
        "alert_reles_desligados": config.alert_reles_desligados,
        "alert_pzem_offline": config.alert_pzem_offline,
        "alert_erro_sistema": config.alert_erro_sistema
    })

@app.route('/config/notificacoes', methods=['POST'])
@login_required
def save_notificacoes_config():
    """Salvar configurações de notificação"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    try:
        print(f"💾 Salvando configurações de notificação...")
        print(f"📦 Dados recebidos: {data}")
        
        # Configurações do Telegram
        if 'telegram_bot_token' in data:
            config.telegram_bot_token = data['telegram_bot_token']
            print(f"   🤖 Token Telegram: {len(data['telegram_bot_token'])} caracteres")
        
        if 'telegram_chat_id' in data:
            config.telegram_chat_id = data['telegram_chat_id']
            print(f"   💬 Chat ID: {data['telegram_chat_id']}")
        
        if 'notify_telegram' in data:
            config.notify_telegram = bool(data['notify_telegram'])
            print(f"   📱 Notificar Telegram: {config.notify_telegram}")
        
        # Configurações de Email
        if 'smtp_server' in data:
            config.smtp_server = data['smtp_server'].strip() if data['smtp_server'] else 'smtp.gmail.com'
            print(f"   📧 SMTP Server: '{config.smtp_server}'")
        
        if 'smtp_port' in data:
            try:
                config.smtp_port = int(data['smtp_port']) if data['smtp_port'] else 587
            except (ValueError, TypeError):
                config.smtp_port = 587
            print(f"   🔌 SMTP Port: {config.smtp_port}")
        
        if 'email_sender' in data:
            config.email_sender = data['email_sender'].strip() if data['email_sender'] else ''
            print(f"   📨 Email Sender: '{config.email_sender}'")
        
        if 'email_password' in data:
            config.email_password = data['email_password'] if data['email_password'] else ''
            print(f"   🔐 Email Password: {'*' * len(data['email_password'])}")
        
        if 'email_notificacao' in data:
            config.email_notificacao = data['email_notificacao'].strip() if data['email_notificacao'] else ''
            print(f"   🎯 Email Notificação: '{config.email_notificacao}'")
        
        if 'notify_email' in data:
            config.notify_email = bool(data['notify_email'])
            print(f"   📧 Notificar Email: {config.notify_email}")
        
        if 'email_frequency' in data:
            config.email_frequency = data['email_frequency'] if data['email_frequency'] else 'immediate'
            print(f"   ⏰ Frequência Email: {config.email_frequency}")
        
        # Configurações do Browser
        if 'notify_browser' in data:
            config.notify_browser = bool(data['notify_browser'])
            print(f"   🔔 Notificar Browser: {config.notify_browser}")
        
        # 🔥 NOVA CONFIGURAÇÃO: Limite de saldo baixo
        if 'saldo_baixo_limite' in data:
            try:
                config.saldo_baixo_limite = float(data['saldo_baixo_limite'])
                print(f"   💰 Limite saldo baixo: {config.saldo_baixo_limite:.1f} kWh")
            except (ValueError, TypeError):
                config.saldo_baixo_limite = 5.0  # Valor padrão
        
        # Alertas específicos
        alertas = [
            'alert_saldo_baixo', 'alert_consumo_pico', 'alert_reles_desligados',
            'alert_pzem_offline', 'alert_erro_sistema'
        ]
        
        for alerta in alertas:
            if alerta in data:
                setattr(config, alerta, bool(data[alerta]))
                print(f"   ⚠️ {alerta}: {bool(data[alerta])}")

        db.session.commit()
        print("✅ Configurações salvas com sucesso!")
        return jsonify({"success": True, "message": "Configurações de notificação salvas com sucesso!"})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao salvar: {str(e)}")
        return jsonify({"success": False, "message": f"Erro ao salvar: {str(e)}"}), 500
    
@app.route('/config/notificacoes/testar', methods=['POST'])
@login_required
def testar_notificacao():
    """Testar notificações"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    tipo = data.get('tipo')
    config = Configuracao.query.first()
    
    try:
        if tipo == 'email':
            return testar_email(config)
        
        elif tipo == 'telegram':
            return testar_telegram(config)
        
        elif tipo == 'browser':
            return jsonify({"success": True, "message": "Notificação de browser configurada!"})
        
        else:
            return jsonify({"success": False, "message": "Tipo de notificação inválido"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao testar notificação: {str(e)}"}), 500

def testar_telegram(config):
    """Testar conexão com Telegram"""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return jsonify({"success": False, "message": "Token do bot ou Chat ID não configurado"})
    
    try:
        import requests
        
        # Testar se o bot token é válido
        bot_info_url = f"https://api.telegram.org/bot{config.telegram_bot_token}/getMe"
        bot_response = requests.get(bot_info_url, timeout=10)
        
        if not bot_response.json().get('ok'):
            return jsonify({"success": False, "message": "Token do bot inválido"})
        
        # Enviar mensagem de teste
        message_url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': config.telegram_chat_id,
            'text': '✅ Teste do Sistema de Energia\nEsta é uma mensagem de teste do seu sistema de monitoramento de energia.',
            'parse_mode': 'HTML'
        }
        
        response = requests.post(message_url, data=payload, timeout=10)
        
        if response.json().get('ok'):
            return jsonify({"success": True, "message": "Mensagem de teste enviada com sucesso para o Telegram!"})
        else:
            error = response.json().get('description', 'Erro desconhecido')
            return jsonify({"success": False, "message": f"Erro ao enviar mensagem: {error}"})
            
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "Timeout na conexão com Telegram"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro de conexão: {str(e)}"})

def testar_email(config):
    """Testar configuração de email"""
    print(f"🔍 Validando configurações de email...")
    print(f"📧 SMTP Server: '{config.smtp_server}'")
    print(f"🔌 SMTP Port: {config.smtp_port}")
    print(f"📨 Email Sender: '{config.email_sender}'")
    print(f"🔐 Email Password: {'*' * len(config.email_password) if config.email_password else 'VAZIO'}")
    print(f"🎯 Email Notificação: '{config.email_notificacao}'")
    
    # 🔥 CORREÇÃO: Validação mais flexível
    if not config.smtp_server or not config.smtp_server.strip():
        # Se não tem SMTP server, usar padrão do Gmail
        config.smtp_server = "smtp.gmail.com"
        print("⚠️  SMTP Server não configurado, usando padrão: smtp.gmail.com")
    
    if not config.smtp_port or config.smtp_port <= 0:
        config.smtp_port = 587
        print("⚠️  Porta SMTP inválida, usando padrão: 587")
    
    if not config.email_sender or not config.email_sender.strip():
        return jsonify({"success": False, "message": "Email de envio não configurado"})
    
    if not config.email_password or not config.email_password.strip():
        return jsonify({"success": False, "message": "Senha do email não configurada"})
    
    if not config.email_notificacao or not config.email_notificacao.strip():
        return jsonify({"success": False, "message": "Email para notificações não configurado"})
    
    try:
        import smtplib
        from email.mime.text import MIMEText  # ✅ CORREÇÃO: MIMEText em maiúsculas
        from email.mime.multipart import MIMEMultipart  # ✅ CORREÇÃO: MIMEMultipart em maiúsculas
        
        # Criar mensagem de teste
        msg = MIMEMultipart()  # ✅ CORREÇÃO
        msg['From'] = config.email_sender
        msg['To'] = config.email_notificacao
        msg['Subject'] = '✅ Teste do Sistema de Energia'
        
        body = f"""
        <h3>Teste do Sistema de Monitoramento de Energia</h3>
        <p>Esta é uma mensagem de teste para verificar a configuração do email.</p>
        <p><strong>Configuração testada:</strong></p>
        <ul>
            <li>Servidor: {config.smtp_server}:{config.smtp_port}</li>
            <li>Email de envio: {config.email_sender}</li>
            <li>Email de destino: {config.email_notificacao}</li>
        </ul>
        <p>Se você recebeu esta mensagem, o sistema de notificações por email está funcionando corretamente!</p>
        <hr>
        <small>Sistema de Automação Residencial - {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
        """
        
        msg.attach(MIMEText(body, 'html'))  # ✅ CORREÇÃO
        
        print(f"🔄 Conectando ao servidor {config.smtp_server}:{config.smtp_port}...")
        
        # Conexão com tratamento de diferentes portas
        if config.smtp_port == 465:
            print("🔒 Usando SSL (porta 465)")
            server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=15)
        else:
            print("🔐 Usando TLS (porta 587)")
            server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=15)
            server.starttls()
        
        print(f"🔐 Efetuando login como {config.email_sender}...")
        server.login(config.email_sender, config.email_password)
        
        print(f"📤 Enviando email para {config.email_notificacao}...")
        text = msg.as_string()
        server.sendmail(config.email_sender, config.email_notificacao, text)
        server.quit()
        
        print(f"✅ Email de teste enviado com sucesso!")
        return jsonify({"success": True, "message": "Email de teste enviado com sucesso!"})
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Erro de autenticação: {str(e)}"
        print(f"❌ {error_msg}")
        
        if "gmail.com" in config.email_sender.lower():
            error_msg += "\n💡 Dica: Use uma SENHA DE APLICATIVO do Gmail, não a senha da conta."
            
        return jsonify({"success": False, "message": error_msg})
    
    except Exception as e:
        error_msg = f"Erro ao enviar email: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "message": error_msg})

@app.route('/config/notificacoes/debug-detalhado', methods=['GET'])
@login_required
def debug_notificacoes_detalhado():
    """Debug detalhado das configurações de notificação"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({"error": "Configuração não encontrada"}), 404
    
    return jsonify({
        "all_config_fields": {
            "smtp_server": {
                "value": config.smtp_server,
                "type": type(config.smtp_server).__name__,
                "is_empty": not bool(config.smtp_server and config.smtp_server.strip())
            },
            "smtp_port": {
                "value": config.smtp_port,
                "type": type(config.smtp_port).__name__
            },
            "email_sender": {
                "value": config.email_sender,
                "type": type(config.email_sender).__name__,
                "is_empty": not bool(config.email_sender and config.email_sender.strip())
            },
            "email_password": {
                "value": "***" if config.email_password else "",
                "length": len(config.email_password) if config.email_password else 0,
                "is_empty": not bool(config.email_password and config.email_password.strip())
            },
            "email_notificacao": {
                "value": config.email_notificacao,
                "type": type(config.email_notificacao).__name__,
                "is_empty": not bool(config.email_notificacao and config.email_notificacao.strip())
            }
        }
    })

# ==========================================================
# SERVIÇO DE NOTIFICAÇÕES - INTEGRAÇÃO COMPLETA
# ==========================================================

class ServicoNotificacoes:
    def __init__(self):
        self.ultima_verificacao = None
        self.alertas_enviados = set()
        self.ultimo_email_diario = None

    def verificar_todas_notificacoes(self):
        """Verifica todos os eventos e envia notificações se necessário"""
        try:
            config = Configuracao.query.first()
            if not config:
                return

            print("🔔 Verificando notificações...")

            # 1. ✅ SALDO BAIXO - COM LIMITE PERSONALIZADO
            if config.alert_saldo_baixo:
                self.verificar_saldo_baixo(config)

            # 2. ✅ CONSUMO EM PICO
            if config.alert_consumo_pico:
                self.verificar_consumo_pico(config)

            # 3. ✅ RELÉS DESLIGADOS
            if config.alert_reles_desligados:
                self.verificar_reles_desligados(config)

            # 4. ✅ PZEM OFFLINE
            if config.alert_pzem_offline:
                self.verificar_pzem_offline(config)

            # 5. ✅ ERROS NO SISTEMA
            if config.alert_erro_sistema:
                self.verificar_erros_sistema(config)

            # Limpar alertas antigos
            self.limpar_alertas_antigos()

        except Exception as e:
            print(f"❌ Erro na verificação de notificações: {e}")

    # ==========================================================
    # 1. SALDO BAIXO - COM LIMITE PERSONALIZADO
    # ==========================================================
    def verificar_saldo_baixo(self, config):
        """Verifica se o saldo está baixo usando o limite personalizado"""
        # 🔥 USA O LIMITE CONFIGURADO PELO USUÁRIO
        limite_saldo_baixo = config.saldo_baixo_limite or 5.0  # kWh
        
        if config.saldo_kwh <= limite_saldo_baixo:
            alerta_id = f"saldo_baixo_{datetime.now().strftime('%Y%m%d%H')}"
            
            if alerta_id not in self.alertas_enviados:
                mensagem = (
                    f"⚠️ **SALDO BAIXO** ⚠️\n"
                    f"Saldo atual: {config.saldo_kwh:.2f} kWh\n"
                    f"Valor: {config.saldo_kwh * config.preco_kwh:.2f} MZN\n"
                    f"Limite configurado: {limite_saldo_baixo} kWh\n"
                    f"⏰ {datetime.now().strftime('%H:%M')}"
                )
                
                self.enviar_notificacao('saldo_baixo', mensagem, config)
                self.alertas_enviados.add(alerta_id)
                print(f"🔔 Alerta de saldo baixo: {config.saldo_kwh:.2f} kWh ≤ {limite_saldo_baixo} kWh")

    # ==========================================================
    # 2. CONSUMO EM PICO
    # ==========================================================
    def verificar_consumo_pico(self, config):
        """Verifica se o consumo está em pico (acima de 80% do limite)"""
        consumo_total = dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power']
        limite_total = config.limite_pzem1 + config.limite_pzem2
        limite_pico = limite_total * 0.8  # 80% do limite total
        
        if consumo_total >= limite_pico:
            alerta_id = f"consumo_pico_{datetime.now().strftime('%Y%m%d%H')}"
            
            if alerta_id not in self.alertas_enviados:
                percentual = (consumo_total / limite_total) * 100
                mensagem = (
                    f"⚡ **CONSUMO EM PICO** ⚡\n"
                    f"Consumo atual: {consumo_total:.0f}W\n"
                    f"Limite do sistema: {limite_total:.0f}W\n"
                    f"Utilização: {percentual:.1f}%\n"
                    f"⏰ {datetime.now().strftime('%H:%M')}"
                )
                
                self.enviar_notificacao('consumo_pico', mensagem, config)
                self.alertas_enviados.add(alerta_id)
                print(f"🔔 Alerta de consumo em pico: {consumo_total:.0f}W")

    # ==========================================================
    # 3. RELÉS DESLIGADOS
    # ==========================================================
    def verificar_reles_desligados(self, config):
        """Verifica se relés foram desligados automaticamente recentemente"""
        # Verifica os comandos pendentes para ver se há relés sendo desligados
        with dados_lock:
            comandos_desligar = [cmd for cmd in comandos_pendentes if cmd.endswith('_OFF')]
        
        if comandos_desligar:
            for comando in comandos_desligar:
                alerta_id = f"rele_desligado_{comando}_{datetime.now().strftime('%Y%m%d%H')}"
                
                if alerta_id not in self.alertas_enviados:
                    rele_id = comando.replace('RELE', '').replace('_OFF', '')
                    mensagem = (
                        f"🔌 **RELÉ DESLIGADO** 🔌\n"
                        f"Relé {rele_id} foi desligado automaticamente\n"
                        f"Motivo: Saldo baixo ou limite atingido\n"
                        f"Saldo atual: {config.saldo_kwh:.2f} kWh\n"
                        f"⏰ {datetime.now().strftime('%H:%M')}"
                    )
                    
                    self.enviar_notificacao('reles_desligados', mensagem, config)
                    self.alertas_enviados.add(alerta_id)
                    print(f"🔔 Alerta de relé desligado: {comando}")

    # ==========================================================
    # 4. PZEM OFFLINE
    # ==========================================================
    def verificar_pzem_offline(self, config):
        """Verifica se algum PZEM está offline"""
        agora = datetime.now(timezone.utc)
        
        for pzem_id in [1, 2]:
            pzem_key = f'pzem{pzem_id}'
            ultima_atualizacao = dados_pzem[pzem_key]['ultima_atualizacao']
            
            if ultima_atualizacao:
                tempo_desconectado = (agora - ultima_atualizacao).total_seconds()
                
                # Considera offline se não atualizou há mais de 2 minutos
                if tempo_desconectado > 120:  # 2 minutos
                    alerta_id = f"pzem_offline_{pzem_id}_{datetime.now().strftime('%Y%m%d%H')}"
                    
                    if alerta_id not in self.alertas_enviados:
                        mensagem = (
                            f"❌ **PZEM OFFLINE** ❌\n"
                            f"PZEM {pzem_id} desconectado\n"
                            f"Tempo offline: {tempo_desconectado/60:.1f} minutos\n"
                            f"Última atualização: {ultima_atualizacao.strftime('%H:%M')}\n"
                            f"⏰ {datetime.now().strftime('%H:%M')}"
                        )
                        
                        self.enviar_notificacao('pzem_offline', mensagem, config)
                        self.alertas_enviados.add(alerta_id)
                        print(f"🔔 Alerta de PZEM offline: {pzem_key}")

    # ==========================================================
    # 5. ERROS NO SISTEMA
    # ==========================================================
    def verificar_erros_sistema(self, config):
        """Monitora erros no sistema"""
        # Esta função pode ser expandida para monitorar logs específicos
        # Por enquanto, é um placeholder para futuras implementações
        pass

    # ==========================================================
    # MÉTODOS DE ENVIO DE NOTIFICAÇÕES
    # ==========================================================
    def enviar_notificacao(self, tipo, mensagem, config):
        """Envia notificação por todos os canais configurados"""
        try:
            # Telegram
            if config.notify_telegram and config.telegram_bot_token and config.telegram_chat_id:
                self.enviar_telegram(mensagem, config)
            
            # Email (apenas para alertas críticos)
            if config.notify_email and tipo in ['saldo_baixo', 'pzem_offline', 'erro_sistema']:
                self.enviar_email(tipo, mensagem, config)
            
            # Browser (sempre que possível)
            if config.notify_browser:
                self.enviar_browser(tipo, mensagem)
                
        except Exception as e:
            print(f"❌ Erro ao enviar notificação: {e}")

    def enviar_telegram(self, mensagem, config):
        """Envia mensagem via Telegram"""
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': config.telegram_chat_id,
                'text': mensagem,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=payload, timeout=10)
            if response.json().get('ok'):
                print("✅ Notificação Telegram enviada")
            else:
                print(f"❌ Erro Telegram: {response.json().get('description')}")
                
        except Exception as e:
            print(f"❌ Erro ao enviar Telegram: {e}")

    def enviar_email(self, tipo, mensagem, config):
        """Envia email de notificação"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Configurar mensagem
            msg = MIMEMultipart()
            msg['From'] = config.email_sender
            msg['To'] = config.email_notificacao
            msg['Subject'] = f"🔔 Alerta do Sistema - {tipo.upper()}"
            
            # Corpo do email
            body = f"""
            <h2>Alerta do Sistema de Energia</h2>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                {mensagem.replace('\n', '<br>')}
            </div>
            <br>
            <small>Sistema de Automação Residencial - {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Enviar email
            if config.smtp_port == 465:
                server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=15)
                server.starttls()
            
            server.login(config.email_sender, config.email_password)
            server.sendmail(config.email_sender, config.email_notificacao, msg.as_string())
            server.quit()
            
            print("✅ Notificação Email enviada")
            
        except Exception as e:
            print(f"❌ Erro ao enviar Email: {e}")

    def enviar_browser(self, tipo, mensagem):
        """Envia notificação no navegador (será capturada pelo JavaScript)"""
        # Esta notificação será processada pelo frontend
        print(f"🔔 Notificação Browser: {tipo} - {mensagem}")

    # ==========================================================
    # LIMPEZA DE ALERTAS ANTIGOS
    # ==========================================================
    def limpar_alertas_antigos(self):
        """Remove alertas antigos do conjunto para evitar duplicação"""
        agora = datetime.now()
        alertas_para_remover = []
        
        for alerta_id in self.alertas_enviados:
            # Remove alertas com mais de 24 horas
            if agora.strftime('%Y%m%d') not in alerta_id:
                alertas_para_remover.append(alerta_id)
        
        for alerta_id in alertas_para_remover:
            self.alertas_enviados.remove(alerta_id)

# ==========================================================
# INICIALIZAÇÃO DO SERVIÇO
# ==========================================================
servico_notificacoes = ServicoNotificacoes()


# ==========================================================
# SISTEMA COMPLETO DE PICOS (DIÁRIO, SEMANAL, MENSAL)
# ==========================================================

def obter_pico_do_dia():
    """Obtém o pico de consumo do dia atual do banco de dados"""
    try:
        hoje = datetime.utcnow().date()
        
        # Buscar pico do PZEM 1
        pico_pzem1 = EnergyData.query.filter(
            EnergyData.pzem_id == 1,
            db.func.date(EnergyData.timestamp) == hoje
        ).order_by(EnergyData.power.desc()).first()
        
        # Buscar pico do PZEM 2
        pico_pzem2 = EnergyData.query.filter(
            EnergyData.pzem_id == 2,
            db.func.date(EnergyData.timestamp) == hoje
        ).order_by(EnergyData.power.desc()).first()
        
        picos = []
        if pico_pzem1:
            picos.append({
                'value': pico_pzem1.power,
                'time': pico_pzem1.timestamp.strftime('%H:%M'),
                'pzem': 1
            })
        if pico_pzem2:
            picos.append({
                'value': pico_pzem2.power,
                'time': pico_pzem2.timestamp.strftime('%H:%M'),
                'pzem': 2
            })
        
        if picos:
            # Encontrar o maior pico
            maior_pico = max(picos, key=lambda x: x['value'])
            return maior_pico
        else:
            # Se não há dados no banco, usar dados em tempo real
            pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
            return {
                'value': pico_atual,
                'time': datetime.now().strftime('%H:%M'),
                'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
            }
            
    except Exception as e:
        print(f"❌ Erro ao obter pico do dia: {e}")
        # Fallback para dados em tempo real
        pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
        return {
            'value': pico_atual,
            'time': datetime.now().strftime('%H:%M'),
            'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
        }

def obter_picos_semana_atual():
    """Obtém os picos de cada dia da semana atual"""
    try:
        hoje = datetime.utcnow().date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())  # Segunda-feira
        dias_semana = []
        picos_semana = []
        labels_semana = []
        
        # Nomes dos dias da semana
        nomes_dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        
        for i in range(7):
            data = inicio_semana + timedelta(days=i)
            dia_nome = nomes_dias[i]
            
            # Se for dia futuro, não buscar
            if data > hoje:
                picos_semana.append(0)
                labels_semana.append(f"{dia_nome}")
                continue
            
            # Buscar picos do dia
            pico_pzem1 = EnergyData.query.filter(
                EnergyData.pzem_id == 1,
                db.func.date(EnergyData.timestamp) == data
            ).order_by(EnergyData.power.desc()).first()
            
            pico_pzem2 = EnergyData.query.filter(
                EnergyData.pzem_id == 2,
                db.func.date(EnergyData.timestamp) == data
            ).order_by(EnergyData.power.desc()).first()
            
            picos_dia = []
            if pico_pzem1:
                picos_dia.append(pico_pzem1.power)
            if pico_pzem2:
                picos_dia.append(pico_pzem2.power)
            
            pico_dia = max(picos_dia) if picos_dia else 0
            picos_semana.append(pico_dia)
            labels_semana.append(f"{dia_nome} ({data.day})")
            
        return {
            "labels": labels_semana,
            "values": picos_semana
        }
        
    except Exception as e:
        print(f"❌ Erro ao obter picos da semana: {e}")
        # Fallback
        return {
            "labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
            "values": [0, 0, 0, 0, 0, 0, 0]
        }

def obter_pico_semanal():
    """Obtém o pico semanal (maior pico da semana atual)"""
    try:
        hoje = datetime.utcnow().date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        
        # Buscar maior pico da semana para PZEM 1
        pico_semana_pzem1 = EnergyData.query.filter(
            EnergyData.pzem_id == 1,
            EnergyData.timestamp >= inicio_semana
        ).order_by(EnergyData.power.desc()).first()
        
        # Buscar maior pico da semana para PZEM 2
        pico_semana_pzem2 = EnergyData.query.filter(
            EnergyData.pzem_id == 2,
            EnergyData.timestamp >= inicio_semana
        ).order_by(EnergyData.power.desc()).first()
        
        picos = []
        if pico_semana_pzem1:
            picos.append({
                'value': pico_semana_pzem1.power,
                'time': pico_semana_pzem1.timestamp.strftime('%d/%m %H:%M'),
                'pzem': 1
            })
        if pico_semana_pzem2:
            picos.append({
                'value': pico_semana_pzem2.power,
                'time': pico_semana_pzem2.timestamp.strftime('%d/%m %H:%M'),
                'pzem': 2
            })
        
        if picos:
            maior_pico = max(picos, key=lambda x: x['value'])
            return maior_pico
        else:
            pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
            return {
                'value': pico_atual,
                'time': datetime.now().strftime('%d/%m %H:%M'),
                'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
            }
            
    except Exception as e:
        print(f"❌ Erro ao obter pico semanal: {e}")
        pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
        return {
            'value': pico_atual,
            'time': datetime.now().strftime('%d/%m %H:%M'),
            'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
        }

def obter_pico_mensal():
    """Obtém o pico mensal (maior pico do mês atual)"""
    try:
        hoje = datetime.utcnow().date()
        inicio_mes = hoje.replace(day=1)
        
        # Buscar maior pico do mês para PZEM 1
        pico_mes_pzem1 = EnergyData.query.filter(
            EnergyData.pzem_id == 1,
            EnergyData.timestamp >= inicio_mes
        ).order_by(EnergyData.power.desc()).first()
        
        # Buscar maior pico do mês para PZEM 2
        pico_mes_pzem2 = EnergyData.query.filter(
            EnergyData.pzem_id == 2,
            EnergyData.timestamp >= inicio_mes
        ).order_by(EnergyData.power.desc()).first()
        
        picos = []
        if pico_mes_pzem1:
            picos.append({
                'value': pico_mes_pzem1.power,
                'time': pico_mes_pzem1.timestamp.strftime('%d/%m %H:%M'),
                'pzem': 1
            })
        if pico_mes_pzem2:
            picos.append({
                'value': pico_mes_pzem2.power,
                'time': pico_mes_pzem2.timestamp.strftime('%d/%m %H:%M'),
                'pzem': 2
            })
        
        if picos:
            maior_pico = max(picos, key=lambda x: x['value'])
            return maior_pico
        else:
            pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
            return {
                'value': pico_atual,
                'time': datetime.now().strftime('%d/%m %H:%M'),
                'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
            }
            
    except Exception as e:
        print(f"❌ Erro ao obter pico mensal: {e}")
        pico_atual = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
        return {
            'value': pico_atual,
            'time': datetime.now().strftime('%d/%m %H:%M'),
            'pzem': 1 if dados_pzem['pzem1']['power'] > dados_pzem['pzem2']['power'] else 2
        }

def obter_energia_atual():
    """Obtém a energia atual (saldo) do sistema"""
    try:
        config = Configuracao.query.first()
        if config:
            return {
                'saldo_kwh': config.saldo_kwh,
                'valor_mzn': config.saldo_kwh * config.preco_kwh,
                'preco_kwh': config.preco_kwh
            }
        else:
            return {
                'saldo_kwh': 0,
                'valor_mzn': 0,
                'preco_kwh': 0.75
            }
    except Exception as e:
        print(f"❌ Erro ao obter energia atual: {e}")
        return {
            'saldo_kwh': 0,
            'valor_mzn': 0,
            'preco_kwh': 0.75
        }
# ==========================================================
# CONTROLE DE RELES
# ==========================================================

def verificar_e_controlar_reles():
    """Liga ou desliga relés AUTOMÁTICOS baseado no saldo kWh"""
    
    config = Configuracao.query.first()
    print("🔍 INICIANDO CONTROLE AUTOMÁTICO DE RELÉS")
    if not config:
        print("❌ Sem configuração encontrada")
        return

    saldo = config.saldo_kwh
    print(f"🔋 SALDO ATUAL: {saldo:.2f} kWh")
    
    reles = Rele.query.all()
    
    for rele in reles:
        print(f"🔌 Analisando {rele.nome}: modo_auto={rele.modo_automatico}, estado={rele.estado}, limite={rele.limite_individual}")

        # 1️⃣ Se está MANUAL → ignorar limites
        if not rele.modo_automatico:
            continue

        # 2️⃣ Proteção contra toque manual
        if rele.ultima_alteracao_manual:
            delta = (datetime.utcnow() - rele.ultima_alteracao_manual).total_seconds()
            if delta < 30:
                print(f"🛡️ Ignorando '{rele.nome}' (alterado manualmente há {delta:.1f}s)")
                continue

        estado_anterior = rele.estado

        # 3️⃣ DESLIGAR se saldo baixo
        if saldo <= rele.limite_individual and rele.estado:
            print(f"⚠️ DESLIGANDO '{rele.nome}' — SALDO({saldo:.2f}) ≤ LIMITE({rele.limite_individual})")
            rele.estado = False

            # 🔥 REGISTRAR LOG
            registrar_log_rele(
                rele.id, 
                True, 
                False, 
                'saldo_baixo', 
                'automatico'
            )

            with dados_lock:
                comandos_pendentes.append(f"RELE{rele.id}_OFF")
            continue

        # 4️⃣ LIGAR se saldo alto
        if saldo > rele.limite_individual and not rele.estado:
            print(f"🟢 LIGANDO '{rele.nome}' — SALDO({saldo:.2f}) > LIMITE({rele.limite_individual})")
            rele.estado = True

            # 🔥 REGISTRAR LOG
            registrar_log_rele(
                rele.id, 
                False, 
                True, 
                'saldo_suficiente', 
                'automatico'
            )

            with dados_lock:
                comandos_pendentes.append(f"RELE{rele.id}_ON")
            continue

    try:
        db.session.commit()
        print("💾 BD actualizada com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao salvar controle automático: {e}")
        db.session.rollback()
# ==========================================================

def verificar_e_controlar_reles_DEBUG():
    """DEBUG TOTAL — Mostra EXACTAMENTE o que o sistema está a fazer"""
    
    print("\n==================== DEBUG DE RELÉS ====================")

    config = Configuracao.query.first()
    if not config:
        print("❌ Sem configuração carregada!")
        return

    saldo = float(config.saldo_kwh)
    print(f"🔋 SALDO GLOBAL ACTUAL: {saldo:.2f} kWh")

    reles = Rele.query.all()

    if not reles:
        print("❌ Nenhum relé encontrado na base de dados!")
        return

    for rele in reles:
        print("\n----------------------------------------------------")
        print(f"🔌 RELÉ: {rele.nome} (ID {rele.id})")
        print(f"📡 Estado actual: {'LIGADO' if rele.estado else 'DESLIGADO'}")
        print(f"⚙ Modo automático: {rele.modo_automatico}")
        print(f"📏 Limite individual: {rele.limite_individual} kWh")
        print(f"🔎 Comparação: SALDO({saldo}) <= LIMITE({rele.limite_individual}) ? → {saldo <= rele.limite_individual}")

        # 1️⃣ MODO MANUAL — ignorar
        if not rele.modo_automatico:
            print("⛔ IGNORADO (modo manual)")
            continue

        # 2️⃣ Verificar bloqueio manual
        if rele.ultima_alteracao_manual:
            delta = (datetime.utcnow() - rele.ultima_alteracao_manual).total_seconds()
            print(f"⏱️ Última alteração manual: {delta:.1f}s atrás")
            if delta < 30:
                print("⛔ Bloqueado — Não agir por 30s após comando manual")
                continue

        # 3️⃣ DESLIGAR se saldo baixo
        if saldo <= rele.limite_individual and rele.estado:
            print("⚠️ AÇÃO: DESLIGAR — SALDO abaixo do limite!")
            rele.estado = False
            
            comando = f"RELE{rele.id}_OFF"
            print(f"➡️ ENVIAR PARA ESP: {comando}")

            with dados_lock:
                comandos_pendentes.append(comando)
            continue

        # 4️⃣ LIGAR se saldo alto
        if saldo > rele.limite_individual and not rele.estado:
            print("🟢 AÇÃO: LIGAR — SALDO acima do limite!")
            rele.estado = True

            comando = f"RELE{rele.id}_ON"
            print(f"➡️ ENVIAR PARA ESP: {comando}")

            with dados_lock:
                comandos_pendentes.append(comando)
            continue

        print("✔ Sem mudanças — Estado já correcto.")

    # Gravar BD
    try:
        db.session.commit()
        print("\n💾 BD actualizada com sucesso!")
    except Exception as e:
        print(f"❌ ERRO ao salvar no BD: {e}")
        db.session.rollback()

    print("========================================================\n")

@app.route('/api/debug/reles', methods=['GET'])
def rota_debug_reles():
    api_key = request.args.get("api_key")

    if api_key not in API_KEYS:
        return jsonify({"error": "Unauthorized"}), 401

    verificar_e_controlar_reles_DEBUG()
    return jsonify({"success": True, "message": "DEBUG executado. Veja o terminal Flask."})

@app.route('/api/debug/reles?api_key=SUA_CHAVE_API_SECRETA')
def debug_reles():
    verificar_e_controlar_reles_DEBUG()
    return jsonify({"success": True, "message": "DEBUG executado. Veja o terminal."})

# ==========================================================

@app.route('/api/reles/verificar-automatico-esp', methods=['POST'])
def verificar_automatico_esp():
    api_key = request.args.get("api_key")

    if api_key not in API_KEYS:
        return jsonify({"success": False, "error": "Unauthorized"})

    print("\n====================")
    print("⚡ API ESP DISPAROU VERIFICAÇÃO AUTOMÁTICA")
    print("====================")

    # AQUI → Chama a função que gera comandos!
    verificar_e_controlar_reles()

    return jsonify({"success": True, "message": "Verificação executada com API_KEY"})

# ==========================================================
# 🔹 /api/reles/<id>/modo  → Alterar entre Modo Manual/Automático
# ==========================================================
@app.route('/api/reles/<int:rele_id>/modo', methods=['POST'])
@login_required
def alterar_modo_rele(rele_id):
    """Altera entre Modo Manual e Automático"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()

    if "modo_automatico" not in data:
        return jsonify({"success": False, "error": "Parâmetro 'modo_automatico' é obrigatório"}), 400

    novo_modo = bool(data["modo_automatico"])
    rele.modo_automatico = novo_modo

    if not novo_modo:
        # Quando entrar no manual → aplicar proteção
        rele.ultima_alteracao_manual = datetime.utcnow()

    try:
        db.session.commit()
        texto = "AUTOMÁTICO" if novo_modo else "MANUAL"
        return jsonify({"success": True, "message": f"Relé '{rele.nome}' agora está em modo {texto}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================================
# 🔹 /api/reles/<id>/toggle-state → Alternar estado (apenas Manual) - CORRIGIDA
# ==========================================================
@app.route('/api/reles/<int:rele_id>/toggle-state', methods=['POST'])
@login_required
def toggle_rele_state(rele_id):
    """Liga/Desliga o relé manualmente (somente em modo Manual)"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    # ⛔ NÃO PERMITE LIGAR/DESLIGAR SE ESTIVER EM AUTOMÁTICO
    if rele.modo_automatico:
        return jsonify({
            "success": False,
            "error": f"O Relé '{rele.nome}' está em modo AUTOMÁTICO. Mude para MANUAL."
        }), 400

    # Alternar estado
    novo_estado = not rele.estado
    rele.estado = novo_estado

    # 🛡️ Aplicar proteção manual por 30 segundos
    rele.ultima_alteracao_manual = datetime.utcnow()

    # Comando para o ESP
    acao = "ON" if novo_estado else "OFF"
    comando = f"RELE{rele.id}_{acao}"

    with dados_lock:
        comandos_pendentes.append(comando)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

    texto = "LIGADO" if novo_estado else "DESLIGADO"
    return jsonify({
        "success": True,
        "message": f"Relé '{rele.nome}' {texto} (Modo Manual)"
    })

# ==========================================================
# 🔹 /api/reles/<id>/estado → Alterar estado (apenas no Manual) - CORRIGIDA
# ==========================================================
@app.route('/api/reles/<int:rele_id>/estado', methods=['POST'])
@login_required
def alterar_estado_rele(rele_id):
    """Altera o estado do relé (apenas funciona em modo Manual)"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    
    if 'estado' not in data:
        return jsonify({"success": False, "error": "Parâmetro 'estado' é obrigatório"}), 400
    
    novo_estado = bool(data['estado'])
    estado_anterior = rele.estado
    
    # ✅ CORREÇÃO: Verifica se está em modo Manual usando o campo correto
    if rele.modo_automatico:
        return jsonify({
            "success": False, 
            "error": f"Relé '{rele.nome}' está em modo AUTOMÁTICO. Mude para MANUAL para controlar manualmente."
        }), 400
    
    # ✅ CORREÇÃO: Só processa se o estado for diferente
    if rele.estado == novo_estado:
        estado_texto = "LIGADO" if novo_estado else "DESLIGADO"
        return jsonify({
            "success": True, 
            "message": f"Relé '{rele.nome}' já está {estado_texto}",
            "rele": rele.to_dict()
        })
    
    # Altera o estado apenas se estiver em modo Manual
    rele.estado = novo_estado
    
    # 🔥 REGISTRAR LOG MANUAL
    registrar_log_rele(
        rele.id, 
        estado_anterior, 
        novo_estado, 
        'manual', 
        'manual'
    )
    
    # Envia comando para o ESP
    acao = "ON" if novo_estado else "OFF"
    comando = f"RELE{rele.id}_{acao}"
    with dados_lock:
        comandos_pendentes.append(comando)
    
    try:
        db.session.commit()
        estado_texto = "LIGADO" if novo_estado else "DESLIGADO"
        return jsonify({
            "success": True, 
            "message": f"Relé '{rele.nome}' {estado_texto} (Modo Manual)",
            "rele": rele.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================================
# 🔹 /api/reles/verificar-automatico → Forçar verificação de relés automáticos
# ==========================================================
@app.route('/api/reles/verificar-automatico', methods=['POST'])
@login_required
def forcar_verificacao_reles():
    """Força a verificação e controle dos relés automáticos"""
    try:
        verificar_e_controlar_reles()
        return jsonify({
            "success": True, 
            "message": "Verificação de relés automáticos executada"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================================
# 🔹DEBUG
#===================================================

# -----------------------------
# Rotas de configuração/web
# -----------------------------
@app.route('/config/limites', methods=['POST'])
@login_required
def config_limites_novo():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    if 'pzem1' in data:
        config.limite_pzem1 = float(data['pzem1'])
    if 'pzem2' in data:
        config.limite_pzem2 = float(data['pzem2'])

    db.session.commit()
    return jsonify({"success": True, "message": "Limites salvos com sucesso!"})

@app.route('/config/limites', methods=['GET'])
@login_required
def get_limites():
    config = Configuracao.query.first()
    if not config:
        return jsonify({"pzem1": 1000, "pzem2": 1000})

    return jsonify({
        "pzem1": config.limite_pzem1,
        "pzem2": config.limite_pzem2
    })

# ==========================================================
# 🔹 /config/preco  → Salvar preço da energia
# ==========================================================
@app.route('/config/preco', methods=['POST'])
@login_required
def config_preco_novo():
    data = request.get_json()
    if not data or 'preco_kwh' not in data:
        return jsonify({"success": False, "message": "Preço inválido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    config.preco_kwh = float(data['preco_kwh'])
    db.session.commit()
    return jsonify({"success": True, "message": "Preço atualizado com sucesso!"})

@app.route('/config/preco', methods=['GET'])
@login_required
def get_preco():
    config = Configuracao.query.first()
    if not config:
        return jsonify({"preco_kwh": 12})
    return jsonify({"preco_kwh": config.preco_kwh})

# ==========================================================
# 🔹 /recargas/calcular  → Calcular recarga com taxas atuais
# ==========================================================
def calcular_recarga(valor_mzn, preco_kwh, taxa_lixo=0, taxa_radio=0, iva_percent=16):
    """
    Calcula o valor em kWh baseado nas taxas administrativas
    """
    # Garantir que os valores não são None
    taxa_lixo = taxa_lixo or 0
    taxa_radio = taxa_radio or 0
    iva_percent = iva_percent or 16
    
    # Calcular valor líquido após taxas fixas
    valor_liquido = valor_mzn - taxa_lixo - taxa_radio
    
    # Aplicar IVA
    valor_com_iva = valor_liquido * (1 - iva_percent/100)
    
    # Calcular kWh
    kwh_creditados = valor_com_iva / preco_kwh
    
    return {
        'valor_mzn': valor_mzn,
        'taxa_lixo': taxa_lixo,
        'taxa_radio': taxa_radio,
        'iva_percent': iva_percent,
        'preco_kwh': preco_kwh,
        'kwh_creditados': round(kwh_creditados, 2),
        'valor_liquido': round(valor_liquido, 2),
        'valor_com_iva': round(valor_com_iva, 2)
    }
@app.route('/recargas/calcular', methods=['POST'])
@login_required
def calcular_recarga_route():
    data = request.get_json()
    
    if not data or 'valor_mzn' not in data:
        return jsonify({"success": False, "message": "Valor em MZN é obrigatório"}), 400
    
    config = Configuracao.query.first()
    if not config:
        return jsonify({"success": False, "message": "Configuração não encontrada"}), 400
    
    valor_mzn = float(data['valor_mzn'])
    
    # Usar taxas da configuração
    resultado = calcular_recarga(
        valor_mzn=valor_mzn,
        preco_kwh=config.preco_kwh,
        taxa_lixo=config.taxa_lixo,
        taxa_radio=config.taxa_radio,
        iva_percent=config.iva_percent
    )
    
    return jsonify({"success": True, "resultado": resultado})

# ==========================================================
# 🔹 /saldo/info  → Informações do saldo e previsões
# ==========================================================
@app.route('/saldo/info', methods=['GET'])
@login_required
def info_saldo():
    config = Configuracao.query.first()
    if not config:
        return jsonify({"success": False, "message": "Configuração não encontrada"}), 400
    
    # Calcular consumo médio por hora (baseado no power atual)
    consumo_atual = dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power']
    consumo_medio_hora = consumo_atual / 1000  # Converter W para kWh
    
    # Se não há consumo atual, usar valor padrão
    if consumo_medio_hora <= 0:
        consumo_medio_hora = 0.5  # kWh/hora padrão
    
    # Calcular previsão
    if consumo_medio_hora > 0:
        horas_restantes = config.saldo_kwh / consumo_medio_hora
        data_termino = datetime.now() + timedelta(hours=horas_restantes)
        
        previsao = {
            'horas_restantes': round(horas_restantes, 1),
            'dias_restantes': round(horas_restantes / 24, 1),
            'data_termino': data_termino.strftime("%d/%m/%Y %H:%M"),
            'consumo_medio_hora': round(consumo_medio_hora, 2)
        }
    else:
        previsao = "Indeterminado"
    
    # Valor em MZN restante
    valor_restante_mzn = config.saldo_kwh * config.preco_kwh
    
    return jsonify({
        "success": True,
        "saldo_kwh": round(config.saldo_kwh, 2),
        "valor_restante_mzn": round(valor_restante_mzn, 2),
        "preco_kwh_atual": config.preco_kwh,
        "previsao": previsao,
        "consumo_medio_hora": round(consumo_medio_hora, 2)
    })
# ==========================================================
# 🔹 /recargas  → Criar nova recarga
# ==========================================================
@app.route('/recargas', methods=['POST'])
@login_required
def criar_recarga():
    data = request.get_json()
    
    if not data or 'valor_mzn' not in data:
        return jsonify({"success": False, "message": "Dados incompletos"}), 400
    
    config = Configuracao.query.first()
    if not config:
        return jsonify({"success": False, "message": "Configuração não encontrada"}), 400
    
    valor_mzn = float(data['valor_mzn'])
    
    # Calcular recarga com taxas atuais
    calculo = calcular_recarga(
        valor_mzn=valor_mzn,
        preco_kwh=config.preco_kwh,
        taxa_lixo=config.taxa_lixo,
        taxa_radio=config.taxa_radio,
        iva_percent=config.iva_percent
    )
    
    # Criar recarga
    recarga = Recarga(
        valor_mzn=valor_mzn,
        taxa_lixo=config.taxa_lixo,
        taxa_radio=config.taxa_radio,
        iva_percent=config.iva_percent,
        preco_kwh=config.preco_kwh,
        kwh_creditados=calculo['kwh_creditados'],
        saldo_anterior=config.saldo_kwh,
        saldo_atual=config.saldo_kwh + calculo['kwh_creditados']
    )
    
    # Atualizar saldo
    config.saldo_kwh = recarga.saldo_atual
    
    try:
        db.session.add(recarga)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": f"Recarga de {calculo['kwh_creditados']} kWh adicionada com sucesso!",
            "recarga": recarga.to_dict(),
            "novo_saldo": round(config.saldo_kwh, 2)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao criar recarga: {str(e)}"}), 500

# ==========================================================
# 🔹 /recargas  → Listar recargas
# ==========================================================
@app.route('/recargas', methods=['GET'])
@login_required
def listar_recargas():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    recargas = Recarga.query.order_by(Recarga.criado_em.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        "success": True,
        "recargas": [r.to_dict() for r in recargas.items],
        "total": recargas.total,
        "pages": recargas.pages,
        "current_page": page
    })

# ==========================================================
# 🔹 /config/taxas  → Salvar e obter taxas administrativas
# ==========================================================
@app.route('/config/taxas', methods=['POST'])
@login_required
def config_taxas():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    # Atualizar taxas
    if 'taxa_lixo' in data:
        config.taxa_lixo = float(data['taxa_lixo'])
    if 'taxa_radio' in data:
        config.taxa_radio = float(data['taxa_radio'])
    if 'iva_percent' in data:
        config.iva_percent = float(data['iva_percent'])
    if 'preco_kwh' in data:
        config.preco_kwh = float(data['preco_kwh'])

    db.session.commit()
    return jsonify({"success": True, "message": "Taxas atualizadas com sucesso!"})

@app.route('/config/taxas', methods=['GET'])
@login_required
def get_taxas():
    config = Configuracao.query.first()
    if not config:
        return jsonify({
            "taxa_lixo": 5.0,
            "taxa_radio": 3.0,
            "iva_percent": 16.0,
            "preco_kwh": 0.75
        })
    
    return jsonify({
        "taxa_lixo": config.taxa_lixo,
        "taxa_radio": config.taxa_radio,
        "iva_percent": config.iva_percent,
        "preco_kwh": config.preco_kwh
    })
# -----------------------------
# -----------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# -----------------------------
# Rotas de autenticação
# -----------------------------
@app.route('/autenticacao')
def autenticacao():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('/auth.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash('Email ou senha incorretos', 'danger')
        return redirect(url_for('autenticacao'))

    if not user.is_active:
        flash('Conta desativada', 'warning')
        return redirect(url_for('autenticacao'))

    login_user(user, remember=remember)
    flash('Login realizado com sucesso!', 'success')
    return redirect(url_for('base'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if password != confirm_password:
        flash('As senhas não coincidem', 'danger')
        return redirect(url_for('autenticacao') + '?tab=register')

    if User.query.filter_by(email=email).first():
        flash('Email já cadastrado', 'danger')
        return redirect(url_for('autenticacao') + '?tab=register')

    if User.query.filter_by(username=username).first():
        flash('Nome de usuário já existe', 'danger')
        return redirect(url_for('autenticacao') + '?tab=register')

    new_user = User(username=username, email=email, is_active=True)
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao criar conta. Tente novamente.', 'danger')
        print(f"Erro no registro: {e}")

    return redirect(url_for('autenticacao'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('autenticacao'))

# -----------------------------
# Rotas para ESP8266 (API_KEY)
# -----------------------------

# ==========================================================
# FUNÇÃO DE DECREMENTO DE ENERGIA EM TEMPO REAL
# ==========================================================

def atualizar_saldo_com_consumo():
    """
    ATUALIZA O SALDO DE ENERGIA USANDO A DIFERENÇA DO CONSUMO ACUMULADO
    Versão otimizada para evitar timeout
    """
    try:
        config = Configuracao.query.first()
        if not config:
            return
        
        consumo_desta_vez = 0.0
        saldo_anterior = config.saldo_kwh
        
        # Para cada PZEM, calcula quanto consumiu desde a última vez
        for pzem_id in [1, 2]:
            pzem_key = f'pzem{pzem_id}'
            
            # Verifica se o PZEM está conectado e tem dados válidos
            if (dados_pzem[pzem_key]['conectado'] and 
                dados_pzem[pzem_key].get('energy', 0) > 0):
                
                consumo_atual = dados_pzem[pzem_key]['energy']
                consumo_anterior = ultimo_consumo_conhecido[pzem_key]
                
                # Calcula quanto foi consumido desde a última vez
                if consumo_atual >= consumo_anterior:
                    diferenca_consumo = consumo_atual - consumo_anterior
                    consumo_desta_vez += diferenca_consumo
                
                # Atualiza o último consumo conhecido
                ultimo_consumo_conhecido[pzem_key] = consumo_atual
        
        # Subtrai o consumo desde a última vez do saldo atual
        if consumo_desta_vez > 0.001:  # Só atualiza se consumo > 1 Wh
            config.saldo_kwh -= consumo_desta_vez
            config.saldo_kwh = max(0, config.saldo_kwh)
            
            # Commit rápido apenas se houver mudança significativa
            db.session.commit()
            
            print(f"📉 Consumo: {consumo_desta_vez:.3f} kWh | Saldo: {saldo_anterior:.2f} → {config.saldo_kwh:.2f} kWh")
            
            # ✅✅✅ CORREÇÃO CRÍTICA: Chamar controle de relés após atualizar saldo
            verificar_e_controlar_reles()
            
        else:
            # Rollback para liberar a transação se não houve consumo significativo
            db.session.rollback()
            
    except Exception as e:
        print(f"❌ Erro ao atualizar saldo: {e}")
        db.session.rollback()
    """
    ATUALIZA O SALDO DE ENERGIA USANDO A DIFERENÇA DO CONSUMO ACUMULADO
    Versão otimizada para evitar timeout
    """
    
    try:
        config = Configuracao.query.first()
        if not config:
            return
        
        consumo_desta_vez = 0.0
        saldo_anterior = config.saldo_kwh
        
        # Para cada PZEM, calcula quanto consumiu desde a última vez
        for pzem_id in [1, 2]:
            pzem_key = f'pzem{pzem_id}'
            
            # Verifica se o PZEM está conectado e tem dados válidos
            if (dados_pzem[pzem_key]['conectado'] and 
                dados_pzem[pzem_key].get('energy', 0) > 0):
                
                consumo_atual = dados_pzem[pzem_key]['energy']
                consumo_anterior = ultimo_consumo_conhecido[pzem_key]
                
                # Calcula quanto foi consumido desde a última vez
                if consumo_atual >= consumo_anterior:
                    diferenca_consumo = consumo_atual - consumo_anterior
                    consumo_desta_vez += diferenca_consumo
                    
                    # DEBUG: Mostrar apenas se houve consumo significativo
                    if diferenca_consumo > 0.001:  # Mais de 1 Wh
                        print(f"📊 PZEM{pzem_id}: +{diferenca_consumo:.3f} kWh")
                
                # Atualiza o último consumo conhecido
                ultimo_consumo_conhecido[pzem_key] = consumo_atual
        
        # Subtrai o consumo desde a última vez do saldo atual
        if consumo_desta_vez > 0.001:  # Só atualiza se consumo > 1 Wh
            config.saldo_kwh -= consumo_desta_vez
            config.saldo_kwh = max(0, config.saldo_kwh)
            
            # Commit rápido apenas se houver mudança significativa
            db.session.commit()
            
            print(f"📉 Consumo: {consumo_desta_vez:.3f} kWh | Saldo: {saldo_anterior:.2f} → {config.saldo_kwh:.2f} kWh")
        else:
            # Rollback para liberar a transação se não houve consumo significativo
            db.session.rollback()
            
    except Exception as e:
        print(f"❌ Erro ao atualizar saldo: {e}")
        db.session.rollback()
# ==========================================================
# HELPERS
# ==========================================================
def validar_payload(data):
    if not data:
        print("❌ Payload vazio ou JSON inválido")
        return False, (jsonify({"error": "JSON inválido"}), 400)

    if 'api_key' not in data or data['api_key'] not in API_KEYS:
        print("❌ API_KEY ausente ou inválida")
        return False, (jsonify({"error": "Unauthorized"}), 401)

    return True, None

def preparar_energy_entries(data):
    energy_data_entries = []
    for i in [1, 2]:
        pzem_key = f'pzem{i}'
        if pzem_key in data:
            print(f"📦 Atualizando {pzem_key}: {data[pzem_key]}")
            
            # Atualiza dados em memória
            for k, v in data[pzem_key].items():
                if k in dados_pzem[pzem_key]:
                    dados_pzem[pzem_key][k] = v

            dados_pzem[pzem_key]['conectado'] = True
            dados_pzem[pzem_key]['ultima_atualizacao'] = datetime.now(timezone.utc)

            # SEMPRE cria entrada no banco se o PZEM estiver conectado
            if dados_pzem[pzem_key]['conectado']:
                try:
                    energy_data = EnergyData(
                        pzem_id=i,
                        voltage=float(data[pzem_key].get('voltage', 0)),
                        current=float(data[pzem_key].get('current', 0)),
                        power=float(data[pzem_key].get('power', 0)),
                        energy=float(data[pzem_key].get('energy', 0)),
                        frequency=float(data[pzem_key].get('frequency', 0)),
                        pf=float(data[pzem_key].get('pf', 0)),
                        timestamp=datetime.now(timezone.utc)
                    )
                    energy_data_entries.append(energy_data)
                    print(f"✅ Dados do {pzem_key} preparados para salvar no banco")
                except Exception as e:
                    print(f"❌ Erro ao criar EnergyData para {pzem_key}: {e}")
    
    return energy_data_entries

def salvar_energy_entries(entries):
    if not entries:
        return True
    try:
        for e in entries:
            db.session.add(e)
        db.session.commit()
        print(f"✅ {len(entries)} registros salvos no banco de dados")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar EnergyData no banco: {e}")
        db.session.rollback()
        return False

def atualizar_reles_payload(data):
    """Atualiza estados vindos do ESP — SEM sobrescrever ações manuais"""
    if "reles" not in data:
        return

    print(f"🔔 Payload ESP: {data['reles']}")

    PROTECAO = 30  # segundos

    for r_data in data["reles"]:
        rele = Rele.query.get(r_data["id"])
        if not rele:
            continue

        estado_esp = r_data.get("estado", rele.estado)

        # 🛑 1. Se está em MODO MANUAL → ignorar ESP
        if not rele.modo_automatico:
            print(f"🛑 ESP ignorado — '{rele.nome}' está em MODO MANUAL")
            continue

        # 🛑 2. Se foi alterado manualmente há menos de 30s → ignorar ESP
        if rele.ultima_alteracao_manual:
            delta = (datetime.utcnow() - rele.ultima_alteracao_manual).total_seconds()
            if delta < PROTECAO:
                print(f"🛡️ Proteção ativa — ignorando ESP para '{rele.nome}' ({delta:.1f}s)")
                continue

        # 🔄 Só atualizar se realmente mudou
        if estado_esp != rele.estado:
            print(f"🔄 ESP alterou '{rele.nome}': {rele.estado} → {estado_esp}")
            rele.estado = estado_esp
            rele.ultima_sincronizacao_esp = datetime.utcnow()

    try:
        db.session.commit()
    except:
        db.session.rollback()

@app.route('/api/reles/<int:rele_id>/forcar-sincronizacao', methods=['POST'])
@login_required
def forcar_sincronizacao(rele_id):
    """Força a sincronização de um relé (útil quando há divergências)"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    # Remove proteções e permite sincronização
    rele.bloqueado_para_sincronizacao = False
    rele.ultima_alteracao_manual = None
    
    try:
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"Sincronização do relé '{rele.nome}' liberada",
            "rele": rele.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500               

@app.route('/api/reles/<int:rele_id>/debug-sincronizacao', methods=['GET'])
@login_required
def debug_sincronizacao_rele(rele_id):
    """Debug do estado de sincronização de um relé"""
    PROTECAO_SEGUNDOS = 30

    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    agora = datetime.utcnow()
    tempo_desde_manual = (agora - rele.ultima_alteracao_manual).total_seconds() if rele.ultima_alteracao_manual else None
    protegido = tempo_desde_manual is not None and tempo_desde_manual < PROTECAO_SEGUNDOS

    return jsonify({
        "success": True,
        "rele": {
            "id": rele.id,
            "nome": rele.nome,
            "estado": rele.estado,
            "modo_automatico": rele.modo_automatico,
            "ultima_alteracao_manual": rele.ultima_alteracao_manual.isoformat() if rele.ultima_alteracao_manual else None,
            "ultima_sincronizacao_esp": rele.ultima_sincronizacao_esp.isoformat() if rele.ultima_sincronizacao_esp else None,
            "tempo_desde_manual": tempo_desde_manual,
            "protegido": protegido,
            "protegido_por_mais": max(0, PROTECAO_SEGUNDOS - tempo_desde_manual) if tempo_desde_manual is not None else None
        }
    })


# ==========================================================
# PROCESSADOR DE PAYLOAD - VERSÃO CORRIGIDA
# ==========================================================
def processar_payload(data):
    try:
        with dados_lock:
            print("🔄 Processando payload dos PZEMs...")

            # PASSO 1: Atualizar saldo baseado no consumo acumulado
            atualizar_saldo_com_consumo()  # DESCOMENTE ESTA LINHA!

            # PASSO 2: Preparar registros EnergyData
            energy_entries = preparar_energy_entries(data)

            # PASSO 3: Salvar registros no banco
            success = salvar_energy_entries(energy_entries)
            
            if not success:
                print("❌ Falha ao salvar dados no banco")
                return False

            # PASSO 4: Atualizar estados dos relés (payload)
            atualizar_reles_payload(data)

            # PASSO 5: Verificar e controlar relés em modo automático
            verificar_e_controlar_reles()

            # PASSO 6: Persistir mudanças dos relés
            try:
                db.session.commit()
                print("✅ Estados dos relés atualizados no banco")
            except Exception as e:
                print(f"❌ Erro ao salvar estados dos relés: {e}")
                db.session.rollback()
                return False

            print("✅ Payload processado com sucesso")
            return True

    except Exception as e:
        print(f"❌ Erro inesperado durante o processamento: {e}")
        db.session.rollback()
        return False
# ==========================================================
# ROTA REFACTORADA
# ==========================================================
@app.route('/api/dados', methods=['POST'])
def receber_dados():
    """Rota OTIMIZADA para Railway - Recebe dados do ESP8266"""
    start_time = datetime.now()
    
    try:
        data = request.get_json(force=True, silent=True)
    except Exception as e:
        print(f"❌ Erro ao decodificar JSON: {e}")
        return jsonify({"error": "JSON inválido"}), 400

    # ✅ VALIDAÇÃO ULTRA-RÁPIDA
    if not data or 'api_key' not in data or data['api_key'] not in API_KEYS:
        return jsonify({"error": "Unauthorized"}), 401

    print(f"📡 Dados recebidos do ESP8266 no Railway")

    try:
        # ✅✅✅ PROCESSAMENTO OTIMIZADO PARA RAILWAY
        
        # PASSO 1: Atualizar dados em memória (MUITO RÁPIDO)
        for i in [1, 2]:
            pzem_key = f'pzem{i}'
            if pzem_key in data:
                # Atualização direta sem prints para ser mais rápido
                for k, v in data[pzem_key].items():
                    if k in dados_pzem[pzem_key]:
                        dados_pzem[pzem_key][k] = v
                dados_pzem[pzem_key]['conectado'] = True
                dados_pzem[pzem_key]['ultima_atualizacao'] = datetime.now(timezone.utc)

        # PASSO 2: ✅ ATUALIZAR SALDO (CRÍTICO)
        atualizar_saldo_com_consumo()

        # PASSO 3: Salvar dados históricos de forma ASSÍNCRONA
        energy_entries = []
        for i in [1, 2]:
            pzem_key = f'pzem{i}'
            if pzem_key in data and dados_pzem[pzem_key]['conectado']:
                try:
                    energy_data = EnergyData(
                        pzem_id=i,
                        voltage=float(data[pzem_key].get('voltage', 0)),
                        current=float(data[pzem_key].get('current', 0)),
                        power=float(data[pzem_key].get('power', 0)),
                        energy=float(data[pzem_key].get('energy', 0)),
                        frequency=float(data[pzem_key].get('frequency', 0)),
                        pf=float(data[pzem_key].get('pf', 0)),
                        timestamp=datetime.now(timezone.utc)
                    )
                    energy_entries.append(energy_data)
                except Exception as e:
                    print(f"❌ Erro ao criar EnergyData para {pzem_key}: {e}")

        # ✅ SALVAMENTO EM LOTE (mais eficiente)
        if energy_entries:
            try:
                db.session.bulk_save_objects(energy_entries)
                db.session.commit()
                print(f"💾 {len(energy_entries)} registros salvos no Railway")
            except Exception as e:
                print(f"❌ Erro ao salvar no Railway: {e}")
                db.session.rollback()

        # PASSO 4: Atualizar estados dos relés (SE HOUVER DADOS)
        if 'reles' in data:
            for r in data['reles']:
                rele = Rele.query.get(r['id'])
                if rele and rele.estado != r.get('estado', rele.estado):
                    rele.estado = r.get('estado', rele.estado)
                    # ✅ Log apenas se mudou
                    print(f"🔌 Relé '{rele.nome}': {'LIGADO' if rele.estado else 'DESLIGADO'}")

            # ✅ Commit único para todos os relés
            try:
                db.session.commit()
            except Exception as e:
                print(f"❌ Erro ao salvar estados dos relés: {e}")
                db.session.rollback()

        # PASSO 5: ✅ VERIFICAÇÃO DE NOTIFICAÇÕES (fora do tempo crítico)
        # Mover para fora do tempo de resposta do ESP
        servico_notificacoes.verificar_todas_notificacoes()

        # ✅ RESPOSTA IMEDIATA para o ESP (CRÍTICO)
        response_time = (datetime.now() - start_time).total_seconds()
        
        return jsonify({
            "status": "success", 
            "message": "Dados recebidos no Railway",
            "records_saved": len(energy_entries),
            "processing_time": f"{response_time:.2f}s",
            "environment": "railway"
        }), 200

    except Exception as e:
        print(f"❌ Erro no processamento Railway: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

# ==========================================================
@app.route('/api/debug-dados')
def debug_dados():
    """Rota para debug - mostra últimos registros no banco"""
    try:
        latest_records = EnergyData.query.order_by(EnergyData.timestamp.desc()).limit(10).all()
        result = []
        for record in latest_records:
            result.append({
                'id': record.id,
                'pzem_id': record.pzem_id,
                'power': record.power,
                'energy': record.energy,
                'timestamp': record.timestamp.isoformat()
            })
        
        return jsonify({
            'total_records': EnergyData.query.count(),
            'latest': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Função separada para processamento pesado (pode ser chamada em background)
def processar_dados_em_background(data):
    """Processa dados pesados como salvar no banco"""
    try:
        with app.app_context():
            # Atualizar saldo
            atualizar_saldo_com_consumo()
            
            # Salvar no banco
            energy_entries = preparar_energy_entries(data)
            salvar_energy_entries(energy_entries)
            
            # Controlar relés
            verificar_e_controlar_reles()
            db.session.commit()
            
            print("✅ Processamento em background concluído")
    except Exception as e:
        print(f"❌ Erro em background: {e}")
#======================================
    # ENVIO DE COMANDOS
#======================================
@app.route('/api/comandos', methods=['GET'])
def obter_comandos():
    api_key = request.args.get('api_key')
    if not api_key or api_key not in API_KEYS:
        return jsonify({"error": "Unauthorized"}), 401

    with dados_lock:
        if comandos_pendentes:
            return jsonify({"comando": comandos_pendentes.pop(0)})
    return jsonify({"comando": ""})

# -----------------------------
# Rotas de dashboard e status
# -----------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    with dados_lock:
        consumo_total = dados_pzem['pzem1']['energy'] + dados_pzem['pzem2']['energy']
        meta = 5000
        economia = max(0, ((meta - consumo_total)/meta)*100)
        pico_hoje = max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power'])
        hora_pico = datetime.now().strftime("%H:%M")
        pzem_status = {
            'pzem1': dados_pzem['pzem1']['conectado'],
            'pzem2': dados_pzem['pzem2']['conectado']
        }
        last_update = dados_pzem['pzem1']['ultima_atualizacao'].strftime("%H:%M:%S") if dados_pzem['pzem1']['ultima_atualizacao'] else datetime.now().strftime("%H:%M:%S")
        reles_db = Rele.query.all()
        return render_template('dashboard.html',
                               dados_pzem=dados_pzem,
                               reles=[r.to_dict() for r in reles_db],
                               economia=round(economia,1),
                               pico_hoje=round(pico_hoje,1),
                               hora_pico=hora_pico,
                               now=datetime.now(),
                               pzem_status=pzem_status,
                               last_update=last_update)

@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    with dados_lock:
        reles_db = Rele.query.all()
        
        # Obter dados do banco/histórico
        pico_hoje = obter_pico_do_dia()
        pico_semanal = obter_pico_semanal()
        pico_mensal = obter_pico_mensal()
        picos_semana_atual = obter_picos_semana_atual()
        energia_atual = obter_energia_atual()
        
        # Dados históricos (exemplo - você pode implementar a lógica real)
        historical = {
            "labels": [f"{i}:00" for i in range(24)],
            "values": [dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power'] for i in range(24)]
        }
        
        reles_chart = {
            "labels": [r.nome for r in reles_db],
            "values": [r.estado for r in reles_db]
        }
        
        return jsonify({
            "pzem1": dados_pzem['pzem1'],
            "pzem2": dados_pzem['pzem2'],
            "reles": [r.to_dict() for r in reles_db],
            "historical": historical,
            "peaks": picos_semana_atual,  # ✅ Agora vem do banco - picos de cada dia da semana
            "reles_chart": reles_chart,
            "peak_today": pico_hoje,  # ✅ Pico do dia do banco
            "peak_weekly": pico_semanal,  # ✅ Novo: Pico semanal
            "peak_monthly": pico_mensal,  # ✅ Novo: Pico mensal
            "energia_atual": energia_atual,  # ✅ Energia atual (saldo)
            "savings": 15  # Mantido para compatibilidade
        })

@app.route('/api/status-pzem')
@login_required
def status_pzem():
    with dados_lock:
        agora = datetime.now(timezone.utc)
        return jsonify({
            "pzem1": dados_pzem['pzem1']['ultima_atualizacao'] and (agora - dados_pzem['pzem1']['ultima_atualizacao']).total_seconds() < 60,
            "pzem2": dados_pzem['pzem2']['ultima_atualizacao'] and (agora - dados_pzem['pzem2']['ultima_atualizacao']).total_seconds() < 60
        })

                        # -----------------------------
                        # CRUD Relés
                        # -----------------------------

# ==========================================================
# 🔹 /api/enviar-comando  → Dashboard envia comandos ao ESP
# ==========================================================
@app.route('/api/enviar-comando', methods=['POST'])
@login_required
def enviar_comando():
    data = request.get_json()
    comando = data.get('comando')

    if not comando:
        return jsonify({"success": False, "error": "Comando inválido"}), 400

    with dados_lock:
        comandos_pendentes.append(comando)
    return jsonify({"success": True, "message": "Comando enviado com sucesso"})
@app.route('/api/comandos', methods=['GET'])
def obter_comando_esp():
    api_key = request.args.get("api_key")

    if api_key not in API_KEYS:
        return jsonify({"comando": ""})

    with dados_lock:
        if comandos_pendentes:
            comando = comandos_pendentes.pop(0)
            print(f"➡️ ENTREGANDO COMANDO AO ESP: {comando}")
            return jsonify({"comando": comando})

    return jsonify({"comando": ""})

@app.route('/api/debug/comandos', methods=['GET'])
def debug_comandos():
    api_key = request.args.get("api_key")
    if api_key and api_key in API_KEYS:
        auth = "ESP"
    elif current_user.is_authenticated:
        auth = f"WEB ({current_user.username})"
    else:
        auth = "anónimo"

    with dados_lock:
        return jsonify({
            "auth": auth,
            "quantidade": len(comandos_pendentes),
            "comandos": list(comandos_pendentes)
        })

# ==========================================================
# 🔹 /api/reles (GET) → Listar relés (para ESP e web)
# ==========================================================
@app.route('/api/reles', methods=['GET'])
def listar_reles():
    api_key = request.args.get('api_key')
    if api_key and api_key in API_KEYS:
        # Chamada do ESP8266
        reles = [r.to_dict() for r in Rele.query.all()]
        return jsonify({"success": True, "reles": reles})
    elif current_user.is_authenticated:
        # Chamada do painel web
        reles = [r.to_dict() for r in Rele.query.all()]
        return jsonify({"success": True, "reles": reles})
    else:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
# ==========================================================
# 🔹 /api/reles/<id> (GET) → Obter um relé
# ==========================================================
@app.route('/api/reles/<int:rele_id>', methods=['GET'])
def obter_rele(rele_id):
    api_key = request.args.get('api_key')
    if not api_key and not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    r = Rele.query.get(rele_id)
    if not r:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404
    return jsonify({"success": True, "rele": r.to_dict()})

# ==========================================================
# 🔹 /api/reles (POST) → Criar novo relé
# ==========================================================
@app.route('/api/reles', methods=['POST'])
@login_required
def criar_rele():
    data = request.get_json()
    if not data or not data.get("nome"):
        return jsonify({"success": False, "error": "Nome obrigatório"}), 400

    r = Rele(
        nome=data['nome'],
        pzem_id=data.get('pzem_id', 1),
        estado=data.get('estado', False),
        limite_individual=data.get('limite_individual', 5.0),  # ✅ kWh padrão
        prioridade=data.get('prioridade', 3),
        modo_automatico=data.get('modo_automatico', True)
    )
    try:
        db.session.add(r)
        db.session.commit()
        return jsonify({"success": True, "rele": r.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 /api/reles/<id> (PUT) → Atualizar relé (web)
# ==========================================================
@app.route('/api/reles/<int:rele_id>', methods=['PUT'])
@login_required
def atualizar_rele(rele_id):
    r = Rele.query.get(rele_id)
    if not r:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    r.nome = data.get('nome', r.nome)
    r.pzem_id = data.get('pzem_id', r.pzem_id)
    r.estado = data.get('estado', r.estado)
    r.limite_individual = data.get('limite_individual', r.limite_individual)
    r.prioridade = data.get('prioridade', r.prioridade)
    r.modo_automatico = data.get('modo_automatico', r.modo_automatico)
    
    try:
        db.session.commit()
        return jsonify({"success": True, "rele": r.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 /api/reles/<id> (DELETE) → Excluir relé (web)
# ==========================================================
@app.route('/api/reles/<int:rele_id>', methods=['DELETE'])
@login_required
def deletar_rele(rele_id):
    r = Rele.query.get(rele_id)
    if not r:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404
    try:
        db.session.delete(r)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 ROTAS PARA CONFIGURAÇÃO VIA WEB
# ==========================================================

# ==========================================================
# 🔹 /api/reles/<id>/config  → Configurar limites de um relé - CORRIGIDA
# ==========================================================
@app.route('/api/reles/<int:rele_id>/config', methods=['POST'])
@login_required
def configurar_rele(rele_id):
    """Configurar todos os parâmetros de um relé via web"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400

    # Atualizar nome se fornecido
    if 'nome' in data and data['nome']:
        rele.nome = data['nome']

    # Atualizar PZEM associado se fornecido
    if 'pzem_id' in data:
        try:
            pzem_id = int(data['pzem_id'])
            if pzem_id not in [1, 2]:
                return jsonify({"success": False, "error": "PZEM deve ser 1 ou 2"}), 400
            rele.pzem_id = pzem_id
        except ValueError:
            return jsonify({"success": False, "error": "PZEM ID deve ser um número"}), 400

    # Atualizar prioridade se fornecido
    if 'prioridade' in data:
        try:
            prioridade = int(data['prioridade'])
            if not 1 <= prioridade <= 5:
                return jsonify({"success": False, "error": "Prioridade deve estar entre 1 e 5"}), 400
            rele.prioridade = prioridade
        except ValueError:
            return jsonify({"success": False, "error": "Prioridade deve ser um número entre 1 e 5"}), 400

    # Atualizar limite individual (kWh) se fornecido
    if 'limite_individual' in data:
        try:
            limite = float(data['limite_individual'])
            if limite < 0:
                return jsonify({"success": False, "error": "Limite individual não pode ser negativo"}), 400
            rele.limite_individual = limite
        except ValueError:
            return jsonify({"success": False, "error": "Limite individual deve ser um número"}), 400

    # ✅ CORREÇÃO: Atualizar modo usando o campo correto
    if 'modo_automatico' in data:
        rele.modo_automatico = bool(data['modo_automatico'])

    try:
        db.session.commit()
        
        # Prepara resposta com descrições amigáveis
        modo_texto = "AUTOMÁTICO" if rele.modo_automatico else "MANUAL"
        prioridade_desc = {
            1: "Máxima (Crítico)",
            2: "Alta (Essencial)", 
            3: "Média (Importante)",
            4: "Baixa (Conveniente)",
            5: "Mínima (Opcional)"
        }.get(rele.prioridade, "Desconhecida")
        
        return jsonify({
            "success": True, 
            "message": f"Configurações do relé '{rele.nome}' salvas com sucesso!",
            "rele": rele.to_dict(),
            "descricoes": {
                "modo": modo_texto,
                "prioridade": prioridade_desc
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 /api/reles/configurar-varios  → Configurar múltiplos relés - CORRIGIDA
# ==========================================================
@app.route('/api/reles/configurar-varios', methods=['POST'])
@login_required
def configurar_varios_reles():
    """Configurar múltiplos relés de uma vez via web"""
    data = request.get_json()
    
    if not data or 'reles' not in data:
        return jsonify({"success": False, "error": "Dados incompletos"}), 400
    
    reles_atualizados = []
    erros = []

    for rele_config in data['reles']:
        if 'id' not in rele_config:
            erros.append("ID do relé não especificado")
            continue
            
        rele = Rele.query.get(rele_config['id'])
        if not rele:
            erros.append(f"Relé ID {rele_config['id']} não encontrado")
            continue
        
        try:
            # Atualizar cada campo fornecido
            if 'nome' in rele_config and rele_config['nome']:
                rele.nome = rele_config['nome']
            
            if 'pzem_id' in rele_config:
                pzem_id = int(rele_config['pzem_id'])
                if pzem_id in [1, 2]:
                    rele.pzem_id = pzem_id
            
            if 'prioridade' in rele_config:
                prioridade = int(rele_config['prioridade'])
                if 1 <= prioridade <= 5:
                    rele.prioridade = prioridade
            
            if 'limite_individual' in rele_config:
                limite = float(rele_config['limite_individual'])
                if limite >= 0:
                    rele.limite_individual = limite
            
            # ✅ CORREÇÃO: Remover campo inexistente
            # if 'saldo_minimo_para_desligar' in rele_config:
            #     saldo_minimo = float(rele_config['saldo_minimo_para_desligar'])
            #     if saldo_minimo >= 0:
            #         rele.saldo_minimo_para_desligar = saldo_minimo
            
            # ✅ CORREÇÃO: Usar campo correto
            if 'modo_automatico' in rele_config:
                rele.modo_automatico = bool(rele_config['modo_automatico'])
            
            reles_atualizados.append(rele.id)
            
        except Exception as e:
            erros.append(f"Erro no relé {rele.nome}: {str(e)}")
    
    try:
        db.session.commit()
        mensagem = f"Configurações de {len(reles_atualizados)} relés atualizadas"
        if erros:
            mensagem += f" | {len(erros)} erros"
        
        return jsonify({
            "success": True, 
            "message": mensagem,
            "reles_atualizados": reles_atualizados,
            "erros": erros
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
# ==========================================================
# 🔹 /api/configuracoes/limites-globais  → Configurar limites globais
# ==========================================================
@app.route('/api/configuracoes/limites-globais', methods=['POST'])
@login_required
def configurar_limites_globais():
    """Configurar limites globais do sistema via web"""
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    # Atualizar limites dos PZEMs se fornecidos
    if 'limite_pzem1' in data:
        try:
            limite = float(data['limite_pzem1'])
            if limite >= 0:
                config.limite_pzem1 = limite
        except ValueError:
            return jsonify({"success": False, "error": "Limite PZEM1 deve ser um número"}), 400

    if 'limite_pzem2' in data:
        try:
            limite = float(data['limite_pzem2'])
            if limite >= 0:
                config.limite_pzem2 = limite
        except ValueError:
            return jsonify({"success": False, "error": "Limite PZEM2 deve ser um número"}), 400

    # Atualizar preço da energia se fornecido
    if 'preco_kwh' in data:
        try:
            preco = float(data['preco_kwh'])
            if preco > 0:
                config.preco_kwh = preco
        except ValueError:
            return jsonify({"success": False, "error": "Preço kWh deve ser um número positivo"}), 400

    try:
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": "Configurações globais salvas com sucesso!",
            "configuracoes": {
                "limite_pzem1": config.limite_pzem1,
                "limite_pzem2": config.limite_pzem2,
                "preco_kwh": config.preco_kwh
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/configuracoes/limites-globais', methods=['GET'])
@login_required
def obter_limites_globais():
    """Obter limites globais atuais do sistema"""
    config = Configuracao.query.first()
    if not config:
        return jsonify({
            "limite_pzem1": 1000,
            "limite_pzem2": 1000,
            "preco_kwh": 0.75
        })

    return jsonify({
        "limite_pzem1": config.limite_pzem1,
        "limite_pzem2": config.limite_pzem2,
        "preco_kwh": config.preco_kwh
    })

# ==========================================================
# 🔹 ROTAS PARA DASHBOARD - CONTROLE MANUAL/AUTOMÁTICO
# ==========================================================
# ==========================================================
# 🔹 /api/reles/status-completo → Status completo para dashboard
# ==========================================================
@app.route('/api/reles/status-completo', methods=['GET'])
@login_required
def status_reles_completo():
    """Retorna status completo dos relés para o dashboard"""
    reles = Rele.query.order_by(Rele.prioridade).all()
    config = Configuracao.query.first()
    
    saldo_global = config.saldo_kwh if config else 0
    reles_formatados = []
    
    for rele in reles:
        # Calcular status do limite
        atingiu_limite = saldo_global <= rele.limite_individual
        status_limite = "🔴 CRÍTICO" if atingiu_limite else "🟢 NORMAL"
        
        modo_texto = "Automático" if rele.modo_automatico else "Manual"
        prioridade_desc = {
            1: "Máxima 🔴",
            2: "Alta 🟠", 
            3: "Média 🟡",
            4: "Baixa 🟢",
            5: "Mínima ⚪"
        }.get(rele.prioridade, "Desconhecida")
        
        reles_formatados.append({
            "id": rele.id,
            "nome": rele.nome,
            "pzem_id": rele.pzem_id,
            "estado": rele.estado,
            "prioridade": rele.prioridade,
            "prioridade_desc": prioridade_desc,
            "limite_individual": rele.limite_individual,
            "saldo_global": round(saldo_global, 2),
            "status_limite": status_limite,
            "atingiu_limite": atingiu_limite,
            "modo_automatico": rele.modo_automatico,
            "modo_desc": modo_texto,
            "pode_controlar_manual": not rele.modo_automatico
        })
    
    return jsonify({
        "success": True,
        "saldo_global": round(saldo_global, 2),
        "reles": reles_formatados
    })

# ==========================================================
# 🔹 /api/reles/<id>/toggle-mode → Alternar entre Manual/Automático (CORRIGIDA)
# ==========================================================
@app.route('/api/reles/<int:rele_id>/toggle-mode', methods=['POST'])
@login_required
def toggle_rele_mode(rele_id):
    """Alterna entre modo Manual e Automático"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    try:
        # ✅ CORREÇÃO: Usar o campo correto - modo_automatico
        novo_modo = not rele.modo_automatico
        rele.modo_automatico = novo_modo
        
        db.session.commit()
        
        modo_texto = "AUTOMÁTICO" if novo_modo else "MANUAL"
        mensagem = f"Relé '{rele.nome}' agora está em modo {modo_texto}"
        
        # ✅ Adiciona aviso se mudando para automático sem limite configurado
        if novo_modo and rele.limite_individual <= 0:
            mensagem += " ⚠️ Configure um limite para funcionamento automático"
        
        return jsonify({
            "success": True, 
            "message": mensagem,
            "rele": rele.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao alternar modo do relé {rele_id}: {e}")
        return jsonify({"success": False, "error": f"Erro interno: {str(e)}"}), 500

# ==========================================================
# 🔹 /api/reles/<id>/update-config → Atualizar configuração rápida
# ==========================================================
@app.route('/api/reles/<int:rele_id>/update-config', methods=['POST'])
@login_required
def update_rele_config(rele_id):
    """Atualização rápida de configuração do relé"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    
    # ✅ CORRIGIDO: Atualizar limite individual (kWh)
    if 'limite_individual' in data:
        try:
            limite = float(data['limite_individual'])
            if limite < 0:
                return jsonify({"success": False, "error": "Limite individual não pode ser negativo"}), 400
            rele.limite_individual = limite
        except ValueError:
            return jsonify({"success": False, "error": "Limite individual deve ser um número"}), 400

    try:
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"Configurações do relé '{rele.nome}' atualizadas!",
            "rele": rele.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    
# ==========================================================
# 🔹 /api/sistema/info  → Informações do sistema para dashboard
# ==========================================================
@app.route('/api/sistema/info', methods=['GET'])
@login_required
def sistema_info():
    """Retorna informações do sistema para o dashboard"""
    config = Configuracao.query.first()
    
    # Calcular consumo total
    consumo_total = dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power']
    
    # Calcular previsão
    if consumo_total > 0:
        horas_restantes = config.saldo_kwh / (consumo_total / 1000)
        previsao = f"{horas_restantes:.1f}h"
    else:
        previsao = "Indeterminado"
    
    return jsonify({
        "success": True,
        "saldo_kwh": round(config.saldo_kwh, 2),
        "consumo_atual": round(consumo_total, 1),
        "previsao": previsao,
        "preco_kwh": config.preco_kwh,
        "valor_restante_mzn": round(config.saldo_kwh * config.preco_kwh, 2)
    })
# ==========================================================

# -----------------------------
# Rota de health check (Railway)
# -----------------------------
@app.route('/health')
def health_check():
    """Rota para verificar status do sistema (health check)"""
    try:
        # Testar conexão com a base de dados
        db.session.execute("SELECT 1")
        db_status = "connected"

        return jsonify({
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.now().isoformat(),
            "environment": "production" if os.environ.get('RAILWAY_ENVIRONMENT') else "development"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


# -----------------------------
# Inicialização do banco
# -----------------------------
def init_db():
    """Inicializa o banco de dados e cria dados padrão"""
    try:
        print("🔄 Inicializando banco de dados...")
        db.create_all()
        print("✅ Tabelas criadas/verificadas com sucesso!")

        # Criar usuário admin se não existir
        if not User.query.filter_by(email='admin@example.com').first():
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_active=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)

            # Criar configuração padrão
            config = Configuracao()
            db.session.add(config)

            db.session.commit()
            print("✅ Usuário admin criado: admin@example.com / admin123")
            print("✅ Configuração padrão criada")
        else:
            print("✅ Usuário admin já existe")

    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        db.session.rollback()


@app.cli.command("init-db")
def init_db_command():
    """Comando para inicializar o banco via CLI"""
    with app.app_context():
        init_db()


# -----------------------------
# Inicialização do sistema de notificações
# -----------------------------
def init_notificacoes():
    """Inicializa o sistema de notificações"""
    print("🔔 Sistema de notificações inicializado")
    # Limpa alertas antigos ao iniciar
    servico_notificacoes.limpar_alertas_antigos()


# -----------------------------
# Inicialização automática em produção (Railway / Gunicorn)
# -----------------------------
with app.app_context():
    init_db()
    init_notificacoes()


# -----------------------------
# Execução local (python app.py)
# -----------------------------
if __name__ == '__main__':
    # Para desenvolvimento local
    port = int(os.environ.get('PORT', 5000))
    debug_mode = True  # Local pode ser True

    print(f"🚀 Servidor local iniciado na porta {port}")
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"🔧 Debug: {debug_mode}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)

    with app.app_context():
        init_db()
    init_notificacoes()
    
    # ✅ PORTA DO RAILWAY (OBRIGATÓRIO)
    port = int(os.environ.get('PORT', 5000))
    
    # ✅ DEBUG DESLIGADO no Railway (sempre False)
    debug_mode = False
    
    print(f"🚀 Servidor Railway iniciado na porta {port}")
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print(f"🔧 Debug: {debug_mode}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)