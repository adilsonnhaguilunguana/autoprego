from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from threading import Lock
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

# -----------------------------
# Inicialização do Flask
# -----------------------------

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'autenticacao'



@app.route('/base')
@login_required
def base():
    return render_template('base.html')

@app.route('/td')
@login_required
def td_dashboard():
    return render_template("td.html")


# -----------------------------
# Configurações e dados globais
# -----------------------------
API_KEYS = {"SUA_CHAVE_API_SECRETA": "ESP8266"}

dados_pzem = {
    "pzem1": {"voltage":0, "current": 0, "power": 0, "energy": 0, "frequency": 0, "pf": 0, "limite": 1000, "conectado": False, "ultima_atualizacao": None},
    "pzem2": {"voltage":0, "current": 0, "power": 0, "energy": 0, "frequency": 0, "pf": 0, "limite": 1000, "conectado": False, "ultima_atualizacao": None}
}

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
    prioridade = db.Column(db.Integer, default=3)  # 1=mais importante, 5=menos importante
    limite_individual = db.Column(db.Integer, default=500)  # Limite individual em Watts
    saldo_minimo_para_desligar = db.Column(db.Float, default=0.0)  # Saldo mínimo em kWh para desligar
    desligar_automatico = db.Column(db.Boolean, default=True)  # Se deve desligar automaticamente
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "pzem_id": self.pzem_id,
            "estado": self.estado,
            "prioridade": self.prioridade,
            "limite_individual": self.limite_individual,
            "saldo_minimo_para_desligar": self.saldo_minimo_para_desligar,
            "desligar_automatico": self.desligar_automatico,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

class Configuracao(db.Model):
    __tablename__ = 'configuracoes'
    id = db.Column(db.Integer, primary_key=True)
    limite_pzem1 = db.Column(db.Float, default=1000.0)
    limite_pzem2 = db.Column(db.Float, default=1000.0)
    preco_kwh = db.Column(db.Float, default=0.75)
    taxa_lixo = db.Column(db.Float, default=5.0)  # MZN fixos
    taxa_radio = db.Column(db.Float, default=3.0)  # MZN fixos
    iva_percent = db.Column(db.Float, default=16.0)  # Percentual
    email_notificacao = db.Column(db.String(120), default='admin@example.com')
    notify_email = db.Column(db.Boolean, default=True)
    notify_telegram = db.Column(db.Boolean, default=False)
    saldo_kwh = db.Column(db.Float, default=0.0)
    prioridade_minima_emergencia = db.Column(db.Integer, default=3)

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
# FUNCAO DE DECREMENTO DE ENREGIA EM TEMPO REAL
# ==========================================================
# Variável global para guardar o último consumo acumulado conhecido
ultimo_consumo_conhecido = {"pzem1": 0.0, "pzem2": 0.0}

def atualizar_saldo_com_consumo():
    """
    ATUALIZA O SALDO DE ENERGIA USANDO A DIFERENÇA DO CONSUMO ACUMULADO
    Calcula quanto foi consumido desde a última medição e subtrai do saldo
    """
    global ultimo_consumo_conhecido
    
    with dados_lock:  # Protege contra acesso simultâneo
        try:
            config = Configuracao.query.first()  # Busca as configurações
            if not config:
                return
            
            consumo_desta_vez = 0  # Consumo desde a última verificação
            
            # Para cada PZEM, calcula quanto consumiu desde a última vez
            for pzem_id in [1, 2]:
                pzem_key = f'pzem{pzem_id}'
                
                # Verifica se o PZEM está conectado
                if dados_pzem[pzem_key]['conectado']:
                    consumo_atual = dados_pzem[pzem_key]['energy']  # Consumo acumulado atual
                    consumo_anterior = ultimo_consumo_conhecido[pzem_key]  # Último consumo guardado
                    
                    # Calcula quanto foi consumido desde a última vez
                    if consumo_atual >= consumo_anterior:
                        diferenca_consumo = consumo_atual - consumo_anterior
                        consumo_desta_vez += diferenca_consumo
                        
                        print(f"📊 PZEM{pzem_id}: Consumiu {diferenca_consumo:.3f} kWh desde a última vez")
                    
                    # Atualiza o último consumo conhecido
                    ultimo_consumo_conhecido[pzem_key] = consumo_atual
            
            # Subtrai o consumo desde a última vez do saldo atual
            if consumo_desta_vez > 0:
                saldo_anterior = config.saldo_kwh
                config.saldo_kwh -= consumo_desta_vez
                config.saldo_kwh = max(0, config.saldo_kwh)  # Não deixa ficar negativo
                
                print(f"📉 Consumo desde última vez: {consumo_desta_vez:.3f} kWh | Saldo: {saldo_anterior:.2f} → {config.saldo_kwh:.2f} kWh")
                db.session.commit()
            
        except Exception as e:
            print(f"❌ Erro ao atualizar saldo: {e}")
            db.session.rollback()

# ==========================================================
# CONTROLE DE RELES
# ==========================================================

def verificar_e_controlar_reles():
    """
    VERIFICA O SALDO DE ENERGIA RESTANTE E DESLIGA RELÉS AUTOMATICAMENTE
    SÓ ATUA SOBRE RELÉS EM MODO AUTOMÁTICO
    """
    with dados_lock:  # Protege contra acesso simultâneo
        try:
            config = Configuracao.query.first()  # Busca as configurações
            if not config:
                return
            
            # Busca apenas relés em MODO AUTOMÁTICO
            reles_automaticos = Rele.query.filter_by(
                desligar_automatico=True  # Apenas relés em modo AUTOMÁTICO
            ).order_by(Rele.prioridade).all()
            
            print(f"🔋 Saldo: {config.saldo_kwh:.2f} kWh | Modo Automático: {len(reles_automaticos)} relés")
            
            reles_desligados = []  # Lista para guardar quais relés foram desligados
            
            # ESTRATÉGIA: Desligar relés em MODO AUTOMÁTICO que atingiram seu limite
            for rele in reles_automaticos:
                # Verifica: relé está LIGADO E saldo ≤ limite mínimo configurado
                if (rele.estado and 
                    config.saldo_kwh <= rele.saldo_minimo_para_desligar and 
                    rele.saldo_minimo_para_desligar > 0):
                    
                    # Cria comando para desligar o relé
                    comando = f"RELE{rele.id}_OFF"
                    comandos_pendentes.append(comando)
                    
                    # Marca o relé como desligado no banco
                    rele.estado = False
                    reles_desligados.append(rele.nome)
                    
                    print(f"🤖 [AUTO] Desligando '{rele.nome}' - Saldo ({config.saldo_kwh:.2f}kWh) ≤ Limite ({rele.saldo_minimo_para_desligar}kWh)")
            
            # Se algum relé foi desligado, salva as alterações
            if reles_desligados:
                db.session.commit()
                print(f"✅ {len(reles_desligados)} relés desligados automaticamente")
                
        except Exception as e:
            print(f"❌ Erro no controle automático: {e}")
            db.session.rollback()
# ==========================================================
# 🔹 /api/reles/<id>/modo  → Alterar entre Modo Manual/Automático
# ==========================================================
@app.route('/api/reles/<int:rele_id>/modo', methods=['POST'])
@login_required
def alterar_modo_rele(rele_id):
    """Altera entre Modo Manual e Automático para um relé"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    
    if 'modo_automatico' not in data:
        return jsonify({"success": False, "error": "Parâmetro 'modo_automatico' é obrigatório"}), 400
    
    # True = Automático, False = Manual
    novo_modo = bool(data['modo_automatico'])
    rele.desligar_automatico = novo_modo
    
    try:
        db.session.commit()
        modo_texto = "AUTOMÁTICO" if novo_modo else "MANUAL"
        return jsonify({
            "success": True, 
            "message": f"Relé '{rele.nome}' agora está em modo {modo_texto}",
            "rele": rele.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 /api/reles/<id>/estado  → Alterar estado (apenas no Manual)
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
    
    # Verifica se está em modo Manual
    if rele.desligar_automatico:
        return jsonify({
            "success": False, 
            "error": f"Relé '{rele.nome}' está em modo AUTOMÁTICO. Mude para MANUAL para controlar manualmente."
        }), 400
    
    # Altera o estado apenas se estiver em modo Manual
    rele.estado = novo_estado
    
    # Envia comando para o ESP
    acao = "ON" if novo_estado else "OFF"
    comando = f"RELE{rele.id}_{acao}"
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
# 🔹 /config/notificacoes  → Salvar e obter notificações
# ==========================================================
@app.route('/config/notificacoes', methods=['POST'])
@login_required
def config_notificacoes_novo():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Nenhum dado recebido"}), 400

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)

    if 'email_notificacao' in data:
        config.email_notificacao = data['email_notificacao']
    if 'notify_email' in data:
        config.notify_email = bool(data['notify_email'])
    if 'notify_telegram' in data:
        config.notify_telegram = bool(data['notify_telegram'])

    db.session.commit()
    return jsonify({"success": True, "message": "Configurações de notificação salvas!"})

@app.route('/config/notificacoes', methods=['GET'])
@login_required
def get_notificacoes():
    config = Configuracao.query.first()
    if not config:
        return jsonify({
            "email_notificacao": "admin@example.com",
            "notify_email": True,
            "notify_telegram": False
        })
    return jsonify({
        "email_notificacao": config.email_notificacao,
        "notify_email": config.notify_email,
        "notify_telegram": config.notify_telegram
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

@app.route('/api/dados', methods=['POST'])
def receber_dados():
    """
    RECEBE DADOS DOS PZEMs E ATUALIZA O SISTEMA
    Fluxo: Recebe dados → Atualiza saldo → Controla relés automáticos
    """
    data = request.get_json()
    if not data or 'api_key' not in data or data['api_key'] not in API_KEYS:
        return jsonify({"error": "Unauthorized"}), 401

    with dados_lock:  # Protege contra acesso simultâneo
        try:
            print("🔄 Recebendo dados dos PZEMs...")
            
            # PASSO 1: Atualizar saldo baseado no consumo acumulado
            atualizar_saldo_com_consumo()
            
            # PASSO 2: Atualizar dados dos PZEMs com informações recebidas
            for i in [1, 2]:
                pzem_key = f'pzem{i}'
                if pzem_key in data:
                    # Atualiza todos os campos do PZEM
                    for k, v in data[pzem_key].items():
                        if k in dados_pzem[pzem_key]:
                            dados_pzem[pzem_key][k] = v
                    
                    # Marca como conectado e atualiza timestamp
                    dados_pzem[pzem_key]['conectado'] = True
                    dados_pzem[pzem_key]['ultima_atualizacao'] = datetime.now(timezone.utc)

                    # Salva no banco de dados histórico
                    db.session.add(EnergyData(
                        pzem_id=i,
                        voltage=data[pzem_key]['voltage'],
                        current=data[pzem_key]['current'],
                        power=data[pzem_key]['power'],
                        energy=data[pzem_key]['energy'],  # Consumo acumulado em kWh
                        frequency=data[pzem_key]['frequency'],
                        pf=data[pzem_key]['pf'],
                    ))

            # PASSO 3: Atualizar estados dos relés (se enviados pelo ESP)
            if 'reles' in data:
                for r in data['reles']:
                    rele = Rele.query.get(r['id'])
                    if rele:
                        # Atualiza estado do relé (vindo do ESP)
                        rele.estado = r.get('estado', rele.estado)
                        print(f"🔌 Estado do relé '{rele.nome}': {'LIGADO' if rele.estado else 'DESLIGADO'}")

            # PASSO 4: Verificar e controlar relés em MODO AUTOMÁTICO
            verificar_e_controlar_reles()

            # PASSO 5: Salvar todas as alterações no banco
            db.session.commit()
            
            print("✅ Dados processados com sucesso")
            return jsonify({"status": "success"})
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao processar dados: {e}")
            return jsonify({"error": "Internal server error"}), 500


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
@app.route('/')
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
        historical = {
            "labels": [f"{i}:00" for i in range(24)],
            "values": [dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power'] for i in range(24)]
        }
        peaks = {
            "labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
            "values": [dados_pzem['pzem1']['power'] + dados_pzem['pzem2']['power'] for i in range(7)]
        }
        reles_chart = {
            "labels": [r.nome for r in reles_db],
            "values": [r.estado for r in reles_db]
        }
        peak_today = {
            "value": max(dados_pzem['pzem1']['power'], dados_pzem['pzem2']['power']),
            "time": datetime.now().strftime("%H:%M")
        }
        return jsonify({
            "pzem1": dados_pzem['pzem1'],
            "pzem2": dados_pzem['pzem2'],
            "reles": [r.to_dict() for r in reles_db],
            "historical": historical,
            "peaks": peaks,
            "reles_chart": reles_chart,
            "peak_today": peak_today,
            "savings": 15
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
        limite_individual=data.get('limite_individual', 500), 
        prioridade=data.get('prioridade', 3)
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
# 🔹 /api/reles/<id>/config  → Configurar limites de um relé
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

    # Atualizar limite individual (Watts) se fornecido
    if 'limite_individual' in data:
        try:
            limite = int(data['limite_individual'])
            if limite < 0:
                return jsonify({"success": False, "error": "Limite individual não pode ser negativo"}), 400
            rele.limite_individual = limite
        except ValueError:
            return jsonify({"success": False, "error": "Limite individual deve ser um número inteiro"}), 400

    # Atualizar saldo mínimo para desligar (kWh) se fornecido
    if 'saldo_minimo_para_desligar' in data:
        try:
            saldo_minimo = float(data['saldo_minimo_para_desligar'])
            if saldo_minimo < 0:
                return jsonify({"success": False, "error": "Saldo mínimo não pode ser negativo"}), 400
            rele.saldo_minimo_para_desligar = saldo_minimo
        except ValueError:
            return jsonify({"success": False, "error": "Saldo mínimo deve ser um número"}), 400

    # Atualizar modo (Manual/Automático) se fornecido
    if 'modo_automatico' in data:
        rele.desligar_automatico = bool(data['modo_automatico'])

    try:
        db.session.commit()
        
        # Prepara resposta com descrições amigáveis
        modo_texto = "AUTOMÁTICO" if rele.desligar_automatico else "MANUAL"
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
# 🔹 /api/reles/configurar-varios  → Configurar múltiplos relés
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
                limite = int(rele_config['limite_individual'])
                if limite >= 0:
                    rele.limite_individual = limite
            
            if 'saldo_minimo_para_desligar' in rele_config:
                saldo_minimo = float(rele_config['saldo_minimo_para_desligar'])
                if saldo_minimo >= 0:
                    rele.saldo_minimo_para_desligar = saldo_minimo
            
            if 'modo_automatico' in rele_config:
                rele.desligar_automatico = bool(rele_config['modo_automatico'])
            
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

# -----------------------------
# Inicialização
# -----------------------------
# ==========================================================
# 🔹 ROTAS PARA DASHBOARD - CONTROLE MANUAL/AUTOMÁTICO
# ==========================================================

# ==========================================================
# 🔹 /api/reles/status-completo  → Status completo para dashboard
# ==========================================================
@app.route('/api/reles/status-completo', methods=['GET'])
@login_required
def status_reles_completo():
    """Retorna status completo dos relés para o dashboard"""
    reles = Rele.query.order_by(Rele.prioridade).all()
    config = Configuracao.query.first()
    
    reles_formatados = []
    for rele in reles:
        # Descrições amigáveis
        modo_texto = "Automático" if rele.desligar_automatico else "Manual"
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
            "saldo_minimo_para_desligar": rele.saldo_minimo_para_desligar,
            "modo_automatico": rele.desligar_automatico,
            "modo_desc": modo_texto,
            "pode_controlar_manual": not rele.desligar_automatico
        })
    
    return jsonify({
        "success": True,
        "saldo_atual": round(config.saldo_kwh, 2) if config else 0,
        "reles": reles_formatados
    })

# ==========================================================
# 🔹 /api/reles/<id>/toggle-mod  → Alternar entre Manual/Automático
# ==========================================================
@app.route('/api/reles/<int:rele_id>/toggle-mode', methods=['POST'])
@login_required
def toggle_rele_mode(rele_id):
    """Alterna entre modo Manual e Automático"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    # Alterna o modo
    rele.desligar_automatico = not rele.desligar_automatico
    
    try:
        db.session.commit()
        modo_texto = "AUTOMÁTICO" if rele.desligar_automatico else "MANUAL"
        return jsonify({
            "success": True, 
            "message": f"Relé '{rele.nome}' agora está em modo {modo_texto}",
            "rele": rele.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# 🔹 /api/reles/<id>/toggle-state  → Alternar estado (apenas Manual)
# ==========================================================
@app.route('/api/reles/<int:rele_id>/toggle-state', methods=['POST'])
@login_required
def toggle_rele_state(rele_id):
    """Alterna o estado do relé (apenas funciona em modo Manual)"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    # Verifica se está em modo Manual
    if rele.desligar_automatico:
        return jsonify({
            "success": False, 
            "error": f"Relé '{rele.nome}' está em modo AUTOMÁTICO. Mude para MANUAL para controlar."
        }), 400
    
    # Alterna o estado
    novo_estado = not rele.estado
    rele.estado = novo_estado
    
    # Envia comando para o ESP
    acao = "ON" if novo_estado else "OFF"
    comando = f"RELE{rele.id}_{acao}"
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
# 🔹 /api/reles/<id>/update-config  → Atualizar configuração rápida
# ==========================================================
@app.route('/api/reles/<int:rele_id>/update-config', methods=['POST'])
@login_required
def update_rele_config(rele_id):
    """Atualização rápida de configuração do relé"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "error": "Relé não encontrado"}), 404

    data = request.get_json()
    
    # Atualizar apenas campos específicos para o dashboard
    if 'saldo_minimo_para_desligar' in data:
        try:
            saldo_minimo = float(data['saldo_minimo_para_desligar'])
            if saldo_minimo >= 0:
                rele.saldo_minimo_para_desligar = saldo_minimo
        except ValueError:
            return jsonify({"success": False, "error": "Saldo mínimo deve ser um número"}), 400

    if 'limite_individual' in data:
        try:
            limite = int(data['limite_individual'])
            if limite >= 0:
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

# Função para inicializar o banco
# -----------------------------
def init_db():
    with app.app_context():
        db.create_all()
        
        # Criar usuário admin padrão se não existir
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
            print("✅ Banco inicializado com usuário admin: admin@example.com / admin123")

# -----------------------------
# Inicialização
# -----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
