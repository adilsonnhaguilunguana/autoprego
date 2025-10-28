from flask import Blueprint, render_template,datetime 
from flask_login import login_required, current_user
from models.device import Device
from models.rele import Rele

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    # Obter dispositivos do usuário
    devices = Device.query.filter_by(user_id=current_user.id).all()
    reles = Rele.query.join(Device).filter(Device.user_id == current_user.id).all()
    
    return render_template('dashboard.html', 
                         devices=devices,
                         reles=reles,
                         now=datetime.now())