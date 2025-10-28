from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app_old import db, dados_pzem, comandos_pendentes, dados_lock, API_KEYS
from app_old import EnergyData, Rele, DailyPeak
from datetime import datetime, timezone, timedelta, date
import traceback

api_bp = Blueprint('api', __name__)

# -----------------------------
# ROTAS PARA ESP8266 (API_KEY)
# -----------------------------

def get_pending_commands():
    """Retorna e limpa comandos pendentes"""
    cmds = list(comandos_pendentes)
    comandos_pendentes.clear()
    return cmds

@api_bp.route('/comandos', methods=['GET'])
def obter_comandos():
    """Rota para ESP8266 obter comandos"""
    api_key = request.args.get("api_key")
    if not api_key or api_key not in API_KEYS:
        return jsonify({"error": "Unauthorized"}), 401

    with dados_lock:
        if comandos_pendentes:
            return jsonify({"comando": comandos_pendentes.pop(0)})
    return jsonify({"comando": ""})

# -----------------------------
# FUNÇÕES DE PICOS
# -----------------------------
def update_daily_peak(pzem_id, value, timestamp=None):
    """Atualiza o pico diário no banco, garantindo que nunca diminua, sem commit."""
    with dados_lock:
        if not isinstance(value, (int, float)) or value < 0:
            print(f"Valor inválido para pico diário: pzem_id={pzem_id}, value={value}")
            return
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        today = date.today()
        peak = DailyPeak.query.filter_by(date=today, pzem_id=pzem_id).first()
        
        if peak:
            if value > peak.value:
                peak.value = value
                peak.time = timestamp.time()
                peak.date = today  # Garante consistência
        else:
            peak = DailyPeak(
                date=today,
                pzem_id=pzem_id,
                value=value,
                time=timestamp.time()
            )
            db.session.add(peak)

def get_today_peak():
    """Obtém o pico do dia atual (04/10/2025) exclusivamente da tabela DailyPeak."""
    try:
        today = date.today()
        peaks_today = DailyPeak.query.filter_by(date=today).all()
        
        if not peaks_today:
            return {
                "value": 0.0,
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "pzem": "Nenhum",
                "date": today.strftime("%Y-%m-%d")
            }
        
        max_peak = max(peaks_today, key=lambda p: p.value)
        return {
            "value": max_peak.value,
            "time": max_peak.time.strftime("%H:%M"),
            "pzem": f"PZEM{max_peak.pzem_id:03d}",
            "date": max_peak.date.strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Erro ao obter pico do dia: {e}, Detalhes: {traceback.format_exc()}")
        return {
            "value": 0.0,
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "pzem": "Nenhum",
            "date": today.strftime("%Y-%m-%d")
        }

def get_historical_data():
    """Obtém dados históricos reais das últimas 24 horas"""
    try:
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Buscar todos os dados das últimas 24 horas
        data = EnergyData.query.filter(
            EnergyData.timestamp >= twenty_four_hours_ago
        ).order_by(EnergyData.timestamp.asc()).all()
        
        # Agrupar por hora para simplificar o gráfico
        hourly_data = {}
        for entry in data:
            hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
            if hour_key not in hourly_data:
                hourly_data[hour_key] = []
            hourly_data[hour_key].append(entry.power)
        
        # Calcular média por hora
        labels = []
        values = []
        for hour, powers in sorted(hourly_data.items()):
            if powers:
                labels.append(hour.strftime("%H:%M"))
                values.append(sum(powers) / len(powers))
        
        # Se não há dados suficientes, usar dados atuais
        if len(values) < 6:
            with dados_lock:
                current_power = dados_pzem["pzem1"]["power"] + dados_pzem["pzem2"]["power"]
                if not values:
                    values = [current_power] * 12
                    labels = [f"{(i*2):02d}:00" for i in range(12)]
                else:
                    last_value = values[-1]
                    while len(values) < 12:
                        values.append(last_value)
                        labels.append(f"{(len(values)*2):02d}:00")
        
        return {"labels": labels[-12:], "values": values[-12:]}
        
    except Exception as e:
        print(f"Erro histórico: {e}")
        with dados_lock:
            current_power = dados_pzem["pzem1"]["power"] + dados_pzem["pzem2"]["power"]
            return {
                "labels": [f"{(i*2):02d}:00" for i in range(12)],
                "values": [current_power] * 12
            }

def get_peak_data():
    """Obtém picos de consumo dos últimos 7 dias (último dia = hoje)"""
    try:
        peaks = {"labels": [], "values": []}
        dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        today = datetime.now(timezone.utc).date()
        
        for i in range(7):
            day = today - timedelta(days=6-i)  # 6 dias atrás até hoje
            start = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
            end = datetime.combine(day, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            # Buscar pico máximo do dia
            peak_data = EnergyData.query.filter(
                EnergyData.timestamp >= start,
                EnergyData.timestamp <= end
            ).order_by(EnergyData.power.desc()).first()
            
            peaks["labels"].append(dias_pt[day.weekday()])
            peaks["values"].append(peak_data.power if peak_data else 0)
        
        return peaks
        
    except Exception as e:
        print(f"Erro picos: {e}")
        return {
            "labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
            "values": [0]*7
        }

def get_reles_chart_data():
    """Obtém dados para gráfico de pizza dos relés"""
    try:
        reles_db = Rele.query.all()
        labels = [r.nome for r in reles_db]
        
        with dados_lock:
            total_power = dados_pzem["pzem1"]["power"] + dados_pzem["pzem2"]["power"]
            
            if total_power > 0:
                active_reles = [r for r in reles_db if r.estado]
                if active_reles:
                    base_power = total_power / len(active_reles)
                    values = [base_power if r.estado else 0 for r in reles_db]
                else:
                    values = [total_power / len(reles_db)] * len(reles_db)
            else:
                values = [0] * len(reles_db)
        
        return {"labels": labels, "values": values}
        
    except Exception as e:
        print(f"Erro gráfico relés: {e}")
        return {"labels": [], "values": []}

def calculate_savings():
    """Calcula percentual de economia baseado em consumo real"""
    try:
        daily_target = 5000  # Meta de 5 kWh/dia
        
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        energy_today_pzem1 = EnergyData.query.filter(
            EnergyData.pzem_id == 1,
            EnergyData.timestamp >= start
        ).order_by(EnergyData.timestamp.desc()).first()
        
        energy_today_pzem2 = EnergyData.query.filter(
            EnergyData.pzem_id == 2,
            EnergyData.timestamp >= start
        ).order_by(EnergyData.timestamp.desc()).first()
        
        total_energy = 0
        if energy_today_pzem1:
            total_energy += energy_today_pzem1.energy
        if energy_today_pzem2:
            total_energy += energy_today_pzem2.energy
        
        if total_energy == 0:
            with dados_lock:
                total_energy = dados_pzem["pzem1"]["energy"] + dados_pzem["pzem2"]["energy"]
        
        if total_energy < daily_target:
            savings = ((daily_target - total_energy) / daily_target) * 100
            return min(100, max(0, savings))
        else:
            return 0
            
    except Exception as e:
        print(f"Erro cálculo economia: {e}")
        return 0




@api_bp.route('/dashboard-data')
@login_required

def dashboard_data():
    peak_today = get_today_peak() 
    """Fornece todos os dados para o dashboard"""
    with dados_lock:
        return jsonify({
            "pzem1": dados_pzem["pzem1"],
            "pzem2": dados_pzem["pzem2"],
            "reles": [{
                "id": r.id,
                "nome": r.nome,
                "pzem_id": r.pzem_id,
                "estado": r.estado,
                "prioridade": r.prioridade,
                "limite": r.limite,
                "consumo_atual": 0
            } for r in Rele.query.all()],
            "historical": get_historical_data(),
            "peaks": get_peak_data(),
            "reles_chart": get_reles_chart_data(),
            "peak_today": get_today_peak(),
            "savings": round(calculate_savings(), 1),
            "peak_today" : get_today_peak(),
            "pico_hoje" : peak_today["value"],
            "hora_pico": peak_today["time"]
        })

@api_bp.route('/status-pzem')
@login_required
def status_pzem():
    """Verifica status de conexão dos PZEMs"""
    with dados_lock:
        agora = datetime.now(timezone.utc)
        pzem1 = dados_pzem["pzem1"]["ultima_atualizacao"] and (agora - dados_pzem["pzem1"]["ultima_atualizacao"]).total_seconds() < 60
        pzem2 = dados_pzem["pzem2"]["ultima_atualizacao"] and (agora - dados_pzem["pzem2"]["ultima_atualizacao"]).total_seconds() < 60
        return jsonify({"pzem1": pzem1, "pzem2": pzem2})

# -----------------------------
# CONTROLE DE RELÉS
# -----------------------------
@api_bp.route('/controle-rele/<int:rele_id>', methods=['POST'])
@login_required
def controlar_rele(rele_id):
    """Controla estado de um relé específico"""
    estado = request.json.get("estado")
    rele = Rele.query.get(rele_id)
    
    if not rele:
        return jsonify({"success": False, "message": "Relé não encontrado"}), 404
    
    with dados_lock:
        rele.estado = estado
        db.session.commit()
        comandos_pendentes.append(f"RELE{rele.id}{1 if estado else 0}")
    
    return jsonify({"success": True})

# -----------------------------
# CRUD RELÉS
# -----------------------------
@api_bp.route('/reles', methods=['GET'])
@login_required
def listar_reles():
    """Lista todos os relés"""
    reles_db = Rele.query.all()
    return jsonify({
        "success": True,
        "reles": [{
            "id": r.id,
            "nome": r.nome,
            "pzem_id": r.pzem_id,
            "estado": r.estado,
            "prioridade": r.prioridade,
            "limite": r.limite,
            "consumo_atual": 0
        } for r in reles_db]
    })

@api_bp.route('/reles/<int:rele_id>', methods=['GET'])
@login_required
def get_rele(rele_id):
    """Obtém dados de um relé específico"""
    rele = Rele.query.get(rele_id)
    if rele:
        return jsonify({
            "success": True,
            "rele": {
                "id": rele.id,
                "nome": rele.nome,
                "pzem_id": rele.pzem_id,
                "estado": rele.estado,
                "prioridade": rele.prioridade,
                "limite": rele.limite
            }
        })
    return jsonify({"success": False, "message": "Relé não encontrado"}), 404

@api_bp.route('/reles', methods=['POST'])
@login_required
def criar_rele():
    """Cria um novo relé"""
    data = request.get_json()
    
    if not data.get("nome") or not data.get("pzem_id"):
        return jsonify({"success": False, "message": "Campos obrigatórios faltando"}), 400
    
    try:
        novo_rele = Rele(
            nome=data["nome"],
            pzem_id=data["pzem_id"],
            prioridade=data.get("prioridade", 3),
            limite=data.get("limite", 500),
            estado=data.get("estado", False)
        )
        
        db.session.add(novo_rele)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Relé adicionado com sucesso",
            "rele": novo_rele.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao criar relé: {str(e)}"}), 500

@api_bp.route('/reles/<int:rele_id>', methods=['PUT'])
@login_required
def atualizar_rele(rele_id):
    """Atualiza dados de um relé"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "message": "Relé não encontrado"}), 404
    
    data = request.get_json()
    try:
        rele.nome = data.get("nome", rele.nome)
        rele.pzem_id = data.get("pzem_id", rele.pzem_id)
        rele.prioridade = data.get("prioridade", rele.prioridade)
        rele.limite = data.get("limite", rele.limite)
        
        if "estado" in data:
            rele.estado = data["estado"]
        
        db.session.commit()
        return jsonify({"success": True, "message": "Relé atualizado com sucesso"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao atualizar relé: {str(e)}"}), 500

@api_bp.route('/reles/<int:rele_id>', methods=['DELETE'])
@login_required
def excluir_rele(rele_id):
    """Exclui um relé"""
    rele = Rele.query.get(rele_id)
    if not rele:
        return jsonify({"success": False, "message": "Relé não encontrado"}), 404
    
    try:
        db.session.delete(rele)
        db.session.commit()
        return jsonify({"success": True, "message": "Relé removido com sucesso"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao excluir relé: {str(e)}"}), 500

# -----------------------------
# CONFIGURAÇÕES
# -----------------------------

@api_bp.route('/config/preco', methods=['POST'])
@login_required
def config_preco():
    return jsonify({"success": True, "message": "Preço atualizado com sucesso"})

@api_bp.route('/config/notificacoes', methods=['POST'])
@login_required
def config_notificacoes():
    return jsonify({"success": True, "message": "Configurações de notificação atualizadas"})