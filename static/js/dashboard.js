// Estado global da aplicação
const state = {
    charts: {
        energyChart: null,
        peakChart: null,
        relesChart: null,
        gaugeChart: null
    },
    reles: {
        currentPage: 1,
        perPage: 5,
        allReles: [],
        filteredReles: []
    }
};

// Função utilitária para obter elementos DOM com segurança
function getElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.error(`Elemento ${id} não encontrado`);
        showToast(`Erro: Elemento ${id} não encontrado`, 'danger');
    }
    return element;
}

// Função para exibir notificações com Bootstrap Toast
function showToast(message, type) {
    const toastContainer = getElement('toast-container');
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

// Função de debounce para eventos de busca
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Inicializar gráficos
function inicializarGraficos() {
    const energyCtx = getElement('energyChart')?.getContext('2d');
    if (energyCtx) {
        state.charts.energyChart = new Chart(energyCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Consumo (kWh)',
                    data: [],
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 14, weight: '600' } } },
                    title: { display: true, text: 'Consumo de Energia', font: { size: 16, weight: '700' } }
                },
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'kWh', font: { size: 14, weight: '600' } }, grid: { color: 'rgba(0, 0, 0, 0.1)' } },
                    x: { grid: { color: 'rgba(0, 0, 0, 0.1)' } }
                },
                animation: { duration: 1000, easing: 'easeOutQuart' }
            }
        });
    }

    const peakCtx = getElement('peakChart')?.getContext('2d');
    if (peakCtx) {
        state.charts.peakChart = new Chart(peakCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Pico de Consumo (W)',
                    data: [],
                    backgroundColor: 'rgba(255, 159, 64, 0.7)',
                    borderColor: 'rgb(255, 159, 64)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 14, weight: '600' } } },
                    title: { display: true, text: 'Picos de Consumo', font: { size: 16, weight: '700' } }
                },
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Watts', font: { size: 14, weight: '600' } }, grid: { color: 'rgba(0, 0, 0, 0.1)' } },
                    x: { grid: { color: 'rgba(0, 0, 0, 0.1)' } }
                }
            }
        });
    }

    const relesCtx = getElement('relesChart')?.getContext('2d');
    if (relesCtx) {
        state.charts.relesChart = new Chart(relesCtx, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)',
                        'rgba(255, 159, 64, 0.7)'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 14, weight: '600' } } },
                    title: { display: true, text: 'Distribuição por Relés', font: { size: 16, weight: '700' } }
                },
                cutout: '60%',
                animation: { animateScale: true, animateRotate: true }
            }
        });
    }

    const gaugeCtx = getElement('gaugeChart')?.getContext('2d');
    if (gaugeCtx) {
        state.charts.gaugeChart = new Chart(gaugeCtx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [0, 100],
                    backgroundColor: ['#4caf50', '#f0f0f0'],
                    borderWidth: 0,
                    circumference: 180,
                    rotation: 270
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '80%',
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                animation: { duration: 1000, easing: 'easeOutQuart' }
            }
        });
    }
}

// Atualizar dados do dashboard
async function atualizarDashboard() {
    try {
        const response = await fetch('/api/dashboard-data');
        if (!response.ok) throw new Error('Erro na resposta da API');
        const data = await response.json();

        if (!data || !data.pzem1 || !data.pzem2 || !data.historical || !data.peaks || !data.reles_chart || !data.reles) {
            throw new Error('Dados da API incompletos');
        }

        atualizarDadosPZEM(data);
        atualizarKPIs(data);
        atualizarGraficos(data);
        verificarAlertas(data);
        atualizarTabelaReles(data.reles);

        const lastUpdate = getElement('last-update-time');
        if (lastUpdate) lastUpdate.textContent = new Date().toLocaleTimeString();
    } catch (error) {
        console.error('Erro ao atualizar dashboard:', error);
        showToast('Erro ao carregar dados do dashboard', 'danger');
    }
}

// Atualizar dados dos PZEMs
function atualizarDadosPZEM(data) {
    const elements = {
        voltagePzem1: getElement('voltage-pzem1'),
        currentPzem1: getElement('current-pzem1'),
        powerPzem1: getElement('power-pzem1'),
        energyPzem1: getElement('energy-pzem1'),
        frequencyPzem1: getElement('frequency-pzem1'),
        pfPzem1: getElement('pf-pzem1'),
        limitPzem1: getElement('limit-pzem1'),
        voltagePzem2: getElement('voltage-pzem2'),
        currentPzem2: getElement('current-pzem2'),
        powerPzem2: getElement('power-pzem2'),
        energyPzem2: getElement('energy-pzem2'),
        frequencyPzem2: getElement('frequency-pzem2'),
        pfPzem2: getElement('pf-pzem2'),
        limitPzem2: getElement('limit-pzem2'),
        statusPzem1: getElement('status-pzem-1'),
        statusPzem2: getElement('status-pzem-2')
    };

    if (Object.values(elements).some(el => !el)) return;

    elements.voltagePzem1.textContent = data.pzem1.voltage.toFixed(1) + ' V';
    elements.currentPzem1.textContent = data.pzem1.current.toFixed(3) + ' A';
    elements.powerPzem1.textContent = data.pzem1.power.toFixed(1) + ' W';
    elements.energyPzem1.textContent = data.pzem1.energy.toFixed(3) + ' kWh';
    elements.frequencyPzem1.textContent = data.pzem1.frequency.toFixed(1) + ' Hz';
    elements.pfPzem1.textContent = data.pzem1.pf.toFixed(2);
    elements.limitPzem1.textContent = data.pzem1.limite + ' W';

    elements.voltagePzem2.textContent = data.pzem2.voltage.toFixed(1) + ' V';
    elements.currentPzem2.textContent = data.pzem2.current.toFixed(3) + ' A';
    elements.powerPzem2.textContent = data.pzem2.power.toFixed(1) + ' W';
    elements.energyPzem2.textContent = data.pzem2.energy.toFixed(3) + ' kWh';
    elements.frequencyPzem2.textContent = data.pzem2.frequency.toFixed(1) + ' Hz';
    elements.pfPzem2.textContent = data.pzem2.pf.toFixed(2);
    elements.limitPzem2.textContent = data.pzem2.limite + ' W';

    elements.statusPzem1.textContent = data.pzem1.conectado ? 'Conectado' : 'Desconectado';
    elements.statusPzem1.className = `badge bg-${data.pzem1.conectado ? 'success' : 'danger'}`;
    elements.statusPzem2.textContent = data.pzem2.conectado ? 'Conectado' : 'Desconectado';
    elements.statusPzem2.className = `badge bg-${data.pzem2.conectado ? 'success' : 'danger'}`;
}

// Atualizar KPIs
async function atualizarKPIs(data) {
    const elements = {
        currentPower: getElement('kpi-current-power'),
        todayEnergy: getElement('kpi-today-energy'),
        todayCost: getElement('kpi-today-cost'),
        peakToday: getElement('kpi-peak-today'),
        peakTime: getElement('kpi-peak-time'),
        savings: getElement('kpi-savings')
    };

    if (Object.values(elements).some(el => !el)) return;

    const totalPower = data.pzem1.power + data.pzem2.power;
    const totalEnergy = data.pzem1.energy + data.pzem2.energy;
    let preco_kwh = 1;

    try {
        const res = await fetch('/config/preco');
        const precoData = await res.json();
        if (precoData.preco_kwh !== undefined) {
            preco_kwh = parseFloat(precoData.preco_kwh);
        }
    } catch (err) {
        console.error('Erro ao obter preço da energia:', err);
    }

    const energyCost = totalEnergy * preco_kwh;
    const savingsPercent = data.savings || 0;

    elements.currentPower.textContent = totalPower.toFixed(1) + ' W';
    elements.todayEnergy.textContent = totalEnergy.toFixed(3) + ' kWh';
    elements.todayCost.textContent = `MZN ${energyCost.toFixed(2)}`;
    elements.peakToday.textContent = data.peak_today?.value?.toFixed(1) + ' W' || '0 W';
    elements.peakTime.textContent = data.peak_today?.time || '--:--';
    elements.savings.textContent = savingsPercent.toFixed(0) + '%';
}

// Atualizar gráficos
function atualizarGraficos(data) {
    if (!data.historical?.labels || !data.historical?.values || !data.peaks?.labels || !data.peaks?.values || !data.reles_chart?.labels || !data.reles_chart?.values) {
        console.error('Dados dos gráficos incompletos');
        showToast('Erro ao atualizar gráficos: dados incompletos', 'danger');
        return;
    }

    if (state.charts.energyChart) {
        state.charts.energyChart.data.labels = data.historical.labels;
        state.charts.energyChart.data.datasets[0].data = data.historical.values;
        state.charts.energyChart.update();
    }

    if (state.charts.peakChart) {
        state.charts.peakChart.data.labels = data.peaks.labels;
        state.charts.peakChart.data.datasets[0].data = data.peaks.values;
        state.charts.peakChart.update();
    }

    if (state.charts.relesChart) {
        state.charts.relesChart.data.labels = data.reles_chart.labels;
        state.charts.relesChart.data.datasets[0].data = data.reles_chart.values;
        state.charts.relesChart.update();
    }

    if (state.charts.gaugeChart) {
        const totalPower = data.pzem1.power + data.pzem2.power;
        const maxPower = (data.pzem1.limite + data.pzem2.limite) || 3000;
        const usagePercent = Math.min(100, (totalPower / maxPower) * 100);

        let gaugeColor = '#4caf50';
        if (usagePercent > 80) gaugeColor = '#f44336';
        else if (usagePercent > 60) gaugeColor = '#ff9800';

        state.charts.gaugeChart.data.datasets[0].data = [usagePercent, 100 - usagePercent];
        state.charts.gaugeChart.data.datasets[0].backgroundColor = [gaugeColor, '#f0f0f0'];
        state.charts.gaugeChart.update();

        const gaugeValue = getElement('gaugeValue');
        if (gaugeValue) {
            gaugeValue.textContent = usagePercent.toFixed(0) + '%';
            gaugeValue.style.color = gaugeColor;
        }
    }
}

// Verificar alertas
function verificarAlertas(data) {
    const alertContainer = getElement('alert-container');
    if (!alertContainer) return;

    alertContainer.innerHTML = ''; // Limpar alertas anteriores

    let alertas = [];

    if (!data || !data.pzem1 || !data.pzem2) {
        alertas.push({
            message: 'Dados dos sensores não disponíveis. Verifique a conexão.',
            type: 'danger',
            priority: 1
        });
    } else {
        // Verificações para PZEM 001
        if (!data.pzem1.conectado) {
            alertas.push({
                message: 'PZEM 001 desconectado!',
                type: 'danger',
                priority: 1
            });
        } else {
            if (data.pzem1.power > data.pzem1.limite) {
                alertas.push({
                    message: `PZEM 001 acima do limite! ${data.pzem1.power.toFixed(1)}W > ${data.pzem1.limite}W`,
                    type: 'danger',
                    priority: 1
                });
            }
            if (data.pzem1.voltage < 200 || data.pzem1.voltage > 240) {
                alertas.push({
                    message: `Tensão PZEM 001 anormal: ${data.pzem1.voltage.toFixed(1)}V (faixa normal: 200-240V)`,
                    type: 'warning',
                    priority: 3
                });
            }
            if (data.pzem1.voltage < 180 || data.pzem1.voltage > 250) {
                alertas.push({
                    message: `TENSÃO CRÍTICA PZEM 001: ${data.pzem1.voltage.toFixed(1)}V!`,
                    type: 'danger',
                    priority: 1
                });
            }
            if (data.pzem1.current > 15) {
                alertas.push({
                    message: `Corrente alta no PZEM 001: ${data.pzem1.current.toFixed(3)}A`,
                    type: 'warning',
                    priority: 2
                });
            }
        }

        // Verificações para PZEM 002
        if (!data.pzem2.conectado) {
            alertas.push({
                message: 'PZEM 002 desconectado!',
                type: 'danger',
                priority: 1
            });
        } else {
            if (data.pzem2.power > data.pzem2.limite) {
                alertas.push({
                    message: `PZEM 002 acima do limite! ${data.pzem2.power.toFixed(1)}W > ${data.pzem2.limite}W`,
                    type: 'danger',
                    priority: 1
                });
            }
            if (data.pzem2.voltage < 200 || data.pzem2.voltage > 240) {
                alertas.push({
                    message: `Tensão PZEM 002 anormal: ${data.pzem2.voltage.toFixed(1)}V (faixa normal: 200-240V)`,
                    type: 'warning',
                    priority: 3
                });
            }
            if (data.pzem2.voltage < 180 || data.pzem2.voltage > 250) {
                alertas.push({
                    message: `TENSÃO CRÍTICA PZEM 002: ${data.pzem2.voltage.toFixed(1)}V!`,
                    type: 'danger',
                    priority: 1
                });
            }
            if (data.pzem2.current > 15) {
                alertas.push({
                    message: `Corrente alta no PZEM 002: ${data.pzem2.current.toFixed(3)}A`,
                    type: 'warning',
                    priority: 2
                });
            }
        }
    }

    // Ordenar alertas por prioridade
    alertas.sort((a, b) => (a.priority || 3) - (b.priority || 3));

    // Renderizar alertas
    alertas.forEach(alerta => {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${alerta.type} alert-custom alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');

        const iconClass = alerta.type === 'danger' ? 'bi-exclamation-triangle-fill' :
                         alerta.type === 'warning' ? 'bi-exclamation-circle-fill' : 'bi-info-circle-fill';

        alertDiv.innerHTML = `
            <i class="bi ${iconClass} me-2"></i>
            ${alerta.message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Fechar"></button>
        `;
        alertContainer.appendChild(alertDiv);

        if (alerta.type === 'danger') {
            alertDiv.classList.add('animate-pulse');
        }
    });
}

// Inicializar sistema de alertas
function inicializarSistemaAlertas() {
    if (!document.getElementById('alert-container')) {
        const mainElement = document.querySelector('main') || document.querySelector('.dashboard-container');
        if (mainElement) {
            const alertContainer = document.createElement('div');
            alertContainer.id = 'alert-container';
            alertContainer.className = 'alert-section';
            mainElement.insertBefore(alertContainer, mainElement.firstChild);
        }
    }
}
// ==========================================================
// CONTROLE MANUAL/AUTOMÁTICO DE RELÉS
// ==========================================================

// Estado do controle manual/automático
const releControlState = {
    modos: {},
    atualizando: false
};

// Carregar modos dos relés
async function carregarModosReles() {
    try {
        const response = await fetch('/api/reles/status-completo');
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            data.reles.forEach(rele => {
                releControlState.modos[rele.id] = {
                    modo_automatico: rele.modo_automatico,
                    pode_controlar_manual: rele.pode_controlar_manual,
                    modo_desc: rele.modo_desc,
                    saldo_minimo_para_desligar: rele.saldo_minimo_para_desligar
                };
            });
        }
    } catch (error) {
        console.error('Erro ao carregar modos dos relés:', error);
    }
}

// Alternar entre modo Manual/Automático
async function alternarModoRele(releId) {
    if (releControlState.atualizando) return;
    
    releControlState.atualizando = true;
    try {
        const response = await fetch(`/api/reles/${releId}/toggle-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            await carregarModosReles();
            await carregarReles(); // Recarregar tabela completa
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Erro ao alternar modo:', error);
        showToast('Erro ao alternar modo', 'danger');
    } finally {
        releControlState.atualizando = false;
    }
}

// Alternar estado (apenas modo Manual)
async function alternarEstadoRele(releId, estadoAtual) {
    const releMode = releControlState.modos[releId];
    
    // Verificar se está em modo Manual
    if (!releMode || releMode.modo_automatico) {
        showToast('Relé está em modo AUTOMÁTICO. Mude para MANUAL para controlar.', 'warning');
        return;
    }

    try {
        const response = await fetch(`/api/reles/${releId}/toggle-state`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            await carregarReles();
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Erro ao alternar estado:', error);
        showToast('Erro ao alternar estado', 'danger');
    }
}

// Atualizar limite individual do relé
async function atualizarLimiteRele(releId, novoLimite) {
    try {
        const response = await fetch(`/api/reles/${releId}/update-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                saldo_minimo_para_desligar: parseFloat(novoLimite)
            })
        });

        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showToast(`Limite do relé atualizado para ${novoLimite}kWh`, 'success');
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Erro ao atualizar limite:', error);
        showToast('Erro ao atualizar limite', 'danger');
    }
}
// Carregar relés do servidor
async function carregarReles() {
    const tbody = getElement('reles-table-body');
    const loadingRow = getElement('loading-reles');
    if (!tbody || !loadingRow) return;

    try {
        loadingRow.style.display = '';
        const response = await fetch('/api/reles');
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success && Array.isArray(data.reles)) {
            state.reles.allReles = data.reles;
            state.reles.filteredReles = [...data.reles];
            state.reles.currentPage = 1;
            atualizarTabelaReles();
            atualizarPaginacaoReles();
        } else {
            throw new Error('Dados de relés inválidos');
        }
    } catch (error) {
        console.error('Erro ao carregar relés:', error);
        showToast('Erro ao carregar relés do servidor', 'danger');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-4">
                    <i class="bi bi-exclamation-triangle text-danger" style="font-size: 2rem;"></i>
                    <p class="mt-2">Erro ao carregar relés</p>
                </td>
            </tr>
        `;
    } finally {
        loadingRow.style.display = 'none';
    }
}

// Atualizar tabela de relés
function atualizarTabelaReles(relesData = null) {
    const tbody = getElement('reles-table-body');
    if (!tbody) return;

    if (relesData) {
        state.reles.allReles = relesData;
        state.reles.filteredReles = [...relesData];
        state.reles.currentPage = 1;
    }

    tbody.innerHTML = '';

    if (state.reles.filteredReles.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-4"> <!-- MUDEI: colspan 6 → 7 -->
                    <i class="bi bi-inbox text-muted" style="font-size: 2rem;"></i>
                    <p class="mt-2 text-muted">Nenhum relé encontrado</p>
                </td>
            </tr>
        `;
        return;
    }

    const startIndex = (state.reles.currentPage - 1) * state.reles.perPage;
    const endIndex = startIndex + state.reles.perPage;
    const paginatedReles = state.reles.filteredReles.slice(startIndex, endIndex);

    paginatedReles.forEach(rele => {
        const isManualMode = !rele.modo_automatico; // ADICIONEI
        const modoTexto = isManualMode ? 'Manual' : 'Automático'; // ADICIONEI
        const modoBadge = isManualMode ? 'bg-warning' : 'bg-info'; // ADICIONEI
        
        const tr = document.createElement('tr');
        tr.className = 'animate-fadeIn';
        tr.innerHTML = `
            <td>${rele.nome}</td>
            <td>PZEM ${rele.pzem_id}</td>
            <!-- REMOVI: <td>${(rele.consumo_atual || 0).toFixed(1)} W</td> -->
            <td>
                <span class="badge ${rele.estado ? 'bg-success' : 'bg-secondary'}">
                    ${rele.estado ? 'Ligado' : 'Desligado'}
                </span>
            </td>
            <!-- ADICIONEI COLUNA MODO -->
            <td>
                <span class="badge ${modoBadge}">
                    ${modoTexto}
                </span>
            </td>
            <td>
                <span class="badge badge-priority-${rele.prioridade}">
                    ${rele.prioridade}
                </span>
            </td>
            <!-- MUDEI: W → kWh -->
            <td>${rele.saldo_minimo_para_desligar || rele.limite} kWh</td>
            <td>
                <div class="action-buttons">
                    <!-- MUDEI: Botão condicional + função alterada -->
                    ${isManualMode ? `
                    <button class="btn btn-action ${rele.estado ? 'btn-outline-danger' : 'btn-outline-success'}" 
                            onclick="alternarEstadoRele(${rele.id}, ${rele.estado})" 
                            data-bs-toggle="tooltip" 
                            title="${rele.estado ? 'Desligar' : 'Ligar'}">
                        <i class="bi bi-power"></i>
                    </button>
                    ` : ''}
                    
                    <!-- ADICIONEI: Botão alternar modo -->
                    <button class="btn btn-action ${isManualMode ? 'btn-outline-info' : 'btn-outline-warning'}" 
                            onclick="alternarModoRele(${rele.id})" 
                            data-bs-toggle="tooltip" 
                            title="Alternar para ${isManualMode ? 'Automático' : 'Manual'}">
                        <i class="bi ${isManualMode ? 'bi-cpu' : 'bi-hand-index'}"></i>
                    </button>
                    
                    <button class="btn btn-action btn-outline-primary" 
                            onclick="editarRele(${rele.id})" 
                            data-bs-toggle="tooltip" 
                            title="Editar">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-action btn-outline-danger" 
                            onclick="confirmarExclusaoRele(${rele.id})" 
                            data-bs-toggle="tooltip" 
                            title="Excluir">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Inicializar tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

// Atualizar paginação
function atualizarPaginacaoReles() {
    const pagination = getElement('reles-pagination');
    if (!pagination) return;

    const totalPages = Math.ceil(state.reles.filteredReles.length / state.reles.perPage);

    if (totalPages <= 1) {
        pagination.style.display = 'none';
        return;
    }

    pagination.style.display = 'flex';
    const ul = pagination.querySelector('ul');
    if (!ul) return;

    let html = `
        <li class="page-item ${state.reles.currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="mudarPaginaReles(${state.reles.currentPage - 1}); return false;">Anterior</a>
        </li>
    `;

    for (let i = 1; i <= totalPages; i++) {
        html += `
            <li class="page-item ${state.reles.currentPage === i ? 'active' : ''}">
                <a class="page-link" href="#" onclick="mudarPaginaReles(${i}); return false;">${i}</a>
            </li>
        `;
    }

    html += `
        <li class="page-item ${state.reles.currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="mudarPaginaReles(${state.reles.currentPage + 1}); return false;">Próxima</a>
        </li>
    `;

    ul.innerHTML = html;
}

// Mudar página de relés
function mudarPaginaReles(page) {
    const totalPages = Math.ceil(state.reles.filteredReles.length / state.reles.perPage);
    if (page < 1 || page > totalPages) return;

    state.reles.currentPage = page;
    atualizarTabelaReles();
    atualizarPaginacaoReles();
}

// Filtrar relés
function filtrarReles() {
    const searchInput = getElement('search-reles');
    const filterSelect = getElement('filter-pzem');
    if (!searchInput || !filterSelect) return;

    const searchTerm = searchInput.value.toLowerCase().trim();
    const pzemFilter = filterSelect.value;

    state.reles.filteredReles = state.reles.allReles.filter(rele => {
        const matchesSearch = !searchTerm || rele.nome.toLowerCase().includes(searchTerm);
        const matchesPzem = pzemFilter === 'all' || rele.pzem_id.toString() === pzemFilter;
        return matchesSearch && matchesPzem;
    });

    state.reles.currentPage = 1;
    atualizarTabelaReles();
    atualizarPaginacaoReles();
}

// Controlar relé (ligar/desligar via ESP)
async function toggleRele(releId, estadoAtual) {
    try {
        // Define o comando conforme o estado desejado
        const novoEstado = !estadoAtual;
        const comando = `RELE${releId}${novoEstado ? 'ON' : 'OFF'}`;

        // Envia o comando para o servidor Flask
        const response = await fetch('/api/enviar-comando', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comando })
        });

        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showToast(`Comando enviado: ${comando}`, 'success');
            // Atualiza tabela de relés após pequeno atraso (ESP processar)
            setTimeout(() => carregarReles(), 2000);
        } else {
            showToast(`Erro ao enviar comando: ${data.error || 'Falha desconhecida'}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao enviar comando de relé:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    }
}


// Abrir modal de edição de relé
async function editarRele(releId) {
    try {
        // Mostrar loading no botão ou interface
        const loadingState = showLoadingState(`edit-rele-${releId}`);
        
        const response = await fetch(`/api/reles/${releId}`);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();

        if (data.success && data.rele) {
            const rele = data.rele;
            const elements = {
                id: getElement('edit-rele-id'),
                name: getElement('edit-rele-name'),
                pzem: getElement('edit-rele-pzem'),
                limit: getElement('edit-rele-limit'),
                priority: getElement('edit-rele-priority'),
                mode: getElement('edit-rele-mode') // ✅ NOVO CAMPO ADICIONADO
            };

            // Verificar se todos os elementos existem
            if (Object.values(elements).some(el => !el)) {
                console.error('Elementos do modal de edição não encontrados:', elements);
                showToast('Erro: Formulário de edição incompleto', 'danger');
                return;
            }

            // Preencher formulário com dados do relé
            elements.id.value = rele.id;
            elements.name.value = rele.nome;
            elements.pzem.value = rele.pzem_id;
            elements.limit.value = rele.limite;
            elements.priority.value = rele.prioridade;
            
            // ✅ NOVO: Preencher campo de modo
            elements.mode.value = rele.modo_automatico ? 'auto' : 'manual';

            // Mostrar modal de edição
            const modalElement = getElement('editReleModal');
            if (!modalElement) {
                throw new Error('Modal de edição não encontrado');
            }
            
            const modal = new bootstrap.Modal(modalElement);
            modal.show();

            // Adicionar evento para limpeza quando modal fechar
            modalElement.addEventListener('hidden.bs.modal', function cleanup() {
                // Limpar qualquer estado temporário se necessário
                modalElement.removeEventListener('hidden.bs.modal', cleanup);
            });

            // Log para debug
            console.log(`Editando relé "${rele.nome}":`, {
                id: rele.id,
                pzem: rele.pzem_id,
                limite: rele.limite,
                prioridade: rele.prioridade,
                modo: rele.modo_automatico ? 'Automático' : 'Manual'
            });

        } else {
            throw new Error(data.message || 'Dados do relé não encontrados');
        }

    } catch (error) {
        console.error('Erro ao carregar relé para edição:', error);
        
        // Mensagem de erro mais específica
        let errorMessage = 'Erro de comunicação com o servidor';
        if (error.message.includes('Erro HTTP: 404')) {
            errorMessage = 'Relé não encontrado';
        } else if (error.message.includes('Erro HTTP: 500')) {
            errorMessage = 'Erro interno do servidor';
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        showToast(`Erro ao carregar dados do relé: ${errorMessage}`, 'danger');
    } finally {
        // Garantir que o loading seja removido
        removeLoadingState(`edit-rele-${releId}`);
    }
}
// Salvar edição de relé
async function salvarEdicaoRele() {
    // Obter elementos do formulário
    const elements = {
        id: getElement('edit-rele-id'),
        name: getElement('edit-rele-name'),
        pzem: getElement('edit-rele-pzem'),
        limit: getElement('edit-rele-limit'),
        priority: getElement('edit-rele-priority'),
        mode: getElement('edit-rele-mode')
    };

    // Verificar se todos os elementos existem
    const missingElements = Object.keys(elements).filter(key => !elements[key]);
    if (missingElements.length > 0) {
        console.error('Elementos do formulário não encontrados:', missingElements);
        showToast('Erro: Formulário incompleto. Recarregue a página.', 'danger');
        return;
    }

    // Obter e validar valores
    const releId = elements.id.value;
    const nome = elements.name.value.trim();
    const pzemId = parseInt(elements.pzem.value);
    const limite = parseInt(elements.limit.value);
    const prioridade = parseInt(elements.priority.value);
    const modoAutomatico = elements.mode.value === 'auto';

    // Validações
    if (!nome) {
        showToast('O nome do relé é obrigatório', 'warning');
        elements.name.focus();
        return;
    }

    if (nome.length < 2 || nome.length > 50) {
        showToast('O nome deve ter entre 2 e 50 caracteres', 'warning');
        elements.name.focus();
        return;
    }

    if (isNaN(pzemId) || pzemId < 1 || pzemId > 2) {
        showToast('Selecione um PZEM válido (1 ou 2)', 'warning');
        elements.pzem.focus();
        return;
    }

    if (isNaN(limite) || limite <= 0 || limite > 2000) {
        showToast('O limite deve ser um número entre 1 e 2000 W', 'warning');
        elements.limit.focus();
        return;
    }

    if (isNaN(prioridade) || prioridade < 1 || prioridade > 5) {
        showToast('A prioridade deve ser um número entre 1 e 5', 'warning');
        elements.priority.focus();
        return;
    }

    // Verificar se já existe outro relé com mesmo nome
    const releExistente = state.reles.allReles.find(rele => 
        rele.id !== parseInt(releId) && 
        rele.nome.toLowerCase() === nome.toLowerCase()
    );
    
    if (releExistente) {
        showToast(`Já existe outro relé com o nome "${nome}"`, 'warning');
        elements.name.focus();
        return;
    }

    try {
        // Mostrar loading
        const submitBtn = document.querySelector('#editReleModal button[type="submit"]');
        const originalText = submitBtn?.innerHTML;
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
            submitBtn.disabled = true;
        }

        // Preparar dados
        const dadosAtualizacao = {
            nome: nome,
            pzem_id: pzemId,
            limite: limite,
            prioridade: prioridade,
            modo_automatico: modoAutomatico
        };

        console.log('📤 Enviando atualização do relé:', dadosAtualizacao);

        const response = await fetch(`/api/reles/${releId}`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dadosAtualizacao)
        });

        // ✅ CORREÇÃO: Tratamento robusto da resposta
        let responseData;
        let responseText;

        try {
            responseText = await response.text();
            
            // Tentar fazer parse como JSON
            if (responseText.trim()) {
                responseData = JSON.parse(responseText);
            } else {
                // Resposta vazia - tratar como sucesso se status for 2xx
                if (response.ok) {
                    responseData = { success: true, message: 'Atualizado com sucesso' };
                } else {
                    throw new Error('Resposta vazia do servidor');
                }
            }
        } catch (parseError) {
            console.error('❌ Erro ao fazer parse da resposta:', parseError);
            console.log('📝 Resposta bruta do servidor:', responseText);
            
            // Se for um status de sucesso mas não é JSON, considerar como sucesso
            if (response.ok) {
                responseData = { success: true, message: 'Atualizado com sucesso' };
            } else {
                throw new Error(`Resposta inválida do servidor: ${responseText.substring(0, 200)}`);
            }
        }

        // Restaurar botão
        if (submitBtn) {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }

        // Verificar se a requisição foi bem sucedida
        if (!response.ok) {
            console.error('❌ Erro HTTP:', {
                status: response.status,
                statusText: response.statusText,
                data: responseData
            });
            
            const errorMsg = responseData?.message || 
                            responseData?.error || 
                            `Erro ${response.status}: ${response.statusText}`;
            
            throw new Error(errorMsg);
        }

        // Verificar sucesso na resposta
        if (responseData.success) {
            // Fechar modal
            const modal = bootstrap.Modal.getInstance(getElement('editReleModal'));
            if (modal) {
                modal.hide();
            }
            
            showToast('✅ Relé atualizado com sucesso!', 'success');
            
            // Atualizar dados
            await Promise.all([
                carregarReles(),
                carregarModosReles()
            ]);
            
            console.log('✅ Relé atualizado com sucesso:', {
                id: releId,
                nome: nome,
                modo: modoAutomatico ? 'Automático' : 'Manual'
            });
            
        } else {
            throw new Error(responseData.message || responseData.error || 'Erro desconhecido ao atualizar relé');
        }

    } catch (error) {
        console.error('❌ Erro ao salvar edição do relé:', error);
        
        // Restaurar botão em caso de erro
        const submitBtn = document.querySelector('#editReleModal button[type="submit"]');
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="bi bi-check-circle"></i> Salvar Alterações';
            submitBtn.disabled = false;
        }

        // Mensagens de erro específicas
        let errorMessage = 'Erro ao atualizar relé';
        
        if (error.message.includes('Resposta inválida do servidor')) {
            errorMessage = 'O servidor retornou uma resposta inesperada. Verifique os logs.';
        } else if (error.message.includes('Failed to fetch')) {
            errorMessage = 'Erro de conexão com o servidor. Verifique sua internet.';
        } else if (error.message.includes('Erro 500')) {
            errorMessage = 'Erro interno do servidor. Tente novamente.';
        } else if (error.message.includes('Erro 404')) {
            errorMessage = 'Relé não encontrado no servidor.';
        } else if (error.message.includes('Erro 400')) {
            errorMessage = 'Dados inválidos enviados ao servidor.';
        } else if (error.message.includes('Erro 409')) {
            errorMessage = 'Já existe um relé com este nome.';
        } else {
            errorMessage = error.message;
        }
        
        showToast(`❌ ${errorMessage}`, 'danger');
        
        // Log adicional para debugging
        console.log('🔍 Debug - Dados enviados:', {
            releId: releId,
            nome: nome,
            pzemId: pzemId,
            limite: limite,
            prioridade: prioridade,
            modoAutomatico: modoAutomatico
        });
    }
}
// ✅ FUNÇÃO AUXILIAR PARA MOSTRAR LOADING (se não existir)
function showLoadingState(elementId) {
    const button = document.querySelector(`[onclick*="editarRele(${elementId})"]`);
    if (button) {
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i class="bi bi-hourglass-split"></i>';
        button.disabled = true;
        return { button, originalHTML };
    }
    return null;
}

// ✅ FUNÇÃO AUXILIAR PARA REMOVER LOADING (se não existir)
function removeLoadingState(elementId) {
    const button = document.querySelector(`[onclick*="editarRele(${elementId})"]`);
    if (button && button.disabled) {
        // Buscar o estado original se necessário
        button.innerHTML = '<i class="bi bi-pencil"></i>';
        button.disabled = false;
    }
}

// Confirmar exclusão de relé com modal Bootstrap
function confirmarExclusaoRele(releId) {
    const rele = state.reles.allReles.find(r => r.id === releId);
    if (!rele) {
        showToast('Relé não encontrado', 'warning');
        return;
    }

    // Criar modal dinamicamente
    const modalId = `confirmDeleteModal-${releId}`;
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="${modalId}Label">Confirmar Exclusão</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                    </div>
                    <div class="modal-body">
                        Tem certeza que deseja excluir o relé "${rele.nome}"? Esta ação não pode ser desfeita.
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-danger" onclick="excluirRele(${releId});">Excluir</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    const existingModal = document.getElementById(modalId);
    if (existingModal) existingModal.remove();

    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();

    // Limpar modal após fechar
    document.getElementById(modalId).addEventListener('hidden.bs.modal', () => {
        document.getElementById(modalId).remove();
    });
}
// Excluir relé
async function excluirRele(releId) {
    try {
        const response = await fetch(`/api/reles/${releId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showToast('Relé excluído com sucesso!', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById(`confirmDeleteModal-${releId}`));
            if (modal) modal.hide();
            await carregarReles();
        } else {
            showToast(`Erro ao excluir relé: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao excluir relé:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    }
}
// Adicionar novo relé
async function addRele() {
    const elements = {
        name: getElement('rele-name'),
        pzem: getElement('rele-pzem'),
        limit: getElement('rele-limit'),
        priority: getElement('rele-priority'),
        mode: getElement('rele-mode'), // ✅ Campo de modo adicionado
        form: getElement('add-rele-form')
    };

    // Verificar se todos os elementos existem
    if (Object.values(elements).some(el => !el)) {
        console.error('Elementos do formulário não encontrados');
        showToast('Erro: Formulário incompleto', 'danger');
        return;
    }

    // Obter e validar valores
    const nome = elements.name.value.trim();
    const pzemId = parseInt(elements.pzem.value);
    const limite = parseInt(elements.limit.value);
    const prioridade = parseInt(elements.priority.value);
    const modoAutomatico = elements.mode.value === 'auto'; // ✅ true=Automático, false=Manual

    // Validações completas
    if (!nome) {
        showToast('O nome do relé é obrigatório', 'warning');
        elements.name.focus();
        return;
    }

    if (nome.length < 2 || nome.length > 50) {
        showToast('O nome deve ter entre 2 e 50 caracteres', 'warning');
        elements.name.focus();
        return;
    }

    if (isNaN(pzemId) || pzemId < 1 || pzemId > 2) {
        showToast('Selecione um PZEM válido', 'warning');
        elements.pzem.focus();
        return;
    }

    if (isNaN(limite) || limite <= 0 || limite > 2000) {
        showToast('O limite deve ser um número entre 1 e 2000 W', 'warning');
        elements.limit.focus();
        return;
    }

    if (isNaN(prioridade) || prioridade < 1 || prioridade > 5) {
        showToast('A prioridade deve ser um número entre 1 e 5', 'warning');
        elements.priority.focus();
        return;
    }

    // Verificar se já existe relé com mesmo nome
    const releExistente = state.reles.allReles.find(rele => 
        rele.nome.toLowerCase() === nome.toLowerCase()
    );
    
    if (releExistente) {
        showToast(`Já existe um relé com o nome "${nome}"`, 'warning');
        elements.name.focus();
        return;
    }

    try {
        // Mostrar loading
        const submitBtn = elements.form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Adicionando...';
        submitBtn.disabled = true;

        const response = await fetch('/api/reles', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                nome: nome,
                pzem_id: pzemId,
                limite: limite,
                prioridade: prioridade,
                modo_automatico: modoAutomatico, // ✅ Campo de modo
                estado: false, // Inicia desligado por padrão
                consumo_atual: 0 // Consumo inicial zero
            })
        });

        // Restaurar botão
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Fechar modal e resetar formulário
            const modal = bootstrap.Modal.getInstance(getElement('addReleModal'));
            modal.hide();
            
            elements.form.reset();
            
            showToast('Relé adicionado com sucesso!', 'success');
            
            // Atualizar dados
            await Promise.all([
                carregarReles(),
                carregarModosReles() // ✅ Atualizar modos
            ]);
            
            // Log para debug
            console.log(`Relé "${nome}" adicionado:`, {
                pzem: pzemId,
                limite: limite,
                prioridade: prioridade,
                modo: modoAutomatico ? 'Automático' : 'Manual'
            });
            
        } else {
            throw new Error(data.message || 'Erro desconhecido ao adicionar relé');
        }

    } catch (error) {
        console.error('Erro ao adicionar relé:', error);
        
        // Mensagem de erro mais específica
        let errorMessage = 'Erro de comunicação com o servidor';
        if (error.message.includes('Erro HTTP: 409')) {
            errorMessage = 'Já existe um relé com este nome';
        } else if (error.message.includes('Erro HTTP: 400')) {
            errorMessage = 'Dados inválidos enviados ao servidor';
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        showToast(errorMessage, 'danger');
    }
}
// Exportar dados
function exportData(format) {
    const reportType = getElement('report-type')?.value;
    const reportPeriod = getElement('report-period')?.value;
    const reportPzem = getElement('report-pzem')?.value;
    let startDate, endDate;

    if (reportPeriod === 'custom') {
        startDate = getElement('start-date')?.value;
        endDate = getElement('end-date')?.value;
        if (!startDate || !endDate) {
            showToast('Selecione as datas inicial e final para exportação', 'warning');
            return;
        }
    }

    showToast(`Iniciando exportação em formato ${format.toUpperCase()}...`, 'info');

    fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: reportType,
            period: reportPeriod,
            pzem: reportPzem,
            startDate,
            endDate,
            format
        })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `relatorio_energia_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast(`Relatório exportado com sucesso como ${format.toUpperCase()}!`, 'success');
    })
    .catch(error => {
        console.error('Erro ao exportar dados:', error);
        showToast('Erro ao exportar relatório', 'danger');
    });
}

// Salvar configuração de limites
function salvarConfigLimites() {
    const elements = {
        limitPzem1: getElement('global-limit-pzem1'),
        limitPzem2: getElement('global-limit-pzem2')
    };

    if (Object.values(elements).some(el => !el)) return;

    const limitePzem1 = parseInt(elements.limitPzem1.value);
    const limitePzem2 = parseInt(elements.limitPzem2.value);

    if (isNaN(limitePzem1) || limitePzem1 < 100 || limitePzem1 > 3000 ||
        isNaN(limitePzem2) || limitePzem2 < 100 || limitePzem2 > 3000) {
        showToast('Os limites devem ser números entre 100 e 3000 W', 'warning');
        return;
    }

    fetch('/config/limites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            pzem1: limitePzem1,
            pzem2: limitePzem2
        })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('Limites de consumo salvos com sucesso!', 'success');
            atualizarDashboard(); // Atualizar dashboard para refletir novos limites
        } else {
            showToast(`Erro ao salvar limites: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erro ao salvar limites:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    });
}
function carregarConfigLimites() {
    fetch('/config/limites')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.pzem1) getElement('global-limit-pzem1').value = data.pzem1;
            if (data.pzem2) getElement('global-limit-pzem2').value = data.pzem2;
        })
        .catch(error => {
            console.error('Erro ao carregar limites:', error);
        });
}


// 🔹 Salvar configurações de notificações
function salvarConfigNotificacoes() {
    const elements = {
        notifyEmail: getElement('notify-email'),
        notifyTelegram: getElement('notify-telegram'),
        emailAddress: getElement('notify-email-address')
    };

    if (Object.values(elements).some(el => !el)) return;

    const emailNotificacoes = elements.notifyEmail.checked;
    const telegramNotificacoes = elements.notifyTelegram.checked;
    const email = elements.emailAddress.value.trim();

    if (emailNotificacoes && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showToast('Por favor, informe um email válido', 'warning');
        return;
    }

    fetch('/config/notificacoes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            notify_email: emailNotificacoes,
            notify_telegram: telegramNotificacoes,
            email_notificacao: email
        })
    })
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showToast('Configurações de notificações salvas com sucesso!', 'success');
            } else {
                showToast(`Erro ao salvar configurações: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Erro ao salvar configurações de notificações:', error);
            showToast('Erro de comunicação com o servidor', 'danger');
        });
} 
// 🔹 Carregar dados de notificações ao abrir a página
function carregarConfigNotificacoes() {
    fetch('/config/notificacoes')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            const emailInput = getElement('notify-email-address');
            const emailCheckbox = getElement('notify-email');
            const telegramCheckbox = getElement('notify-telegram');

            if (emailInput && data.email_notificacao)
                emailInput.value = data.email_notificacao;
            if (emailCheckbox)
                emailCheckbox.checked = data.notify_email;
            if (telegramCheckbox)
                telegramCheckbox.checked = data.notify_telegram;
        })
        .catch(error => console.error('Erro ao carregar configurações de notificações:', error));
}

// ==========================================================
// CONFIGURAÇÕES - RECARGAS E TAXAS
// ==========================================================

// 🔹 Carregar configurações de taxas
function carregarConfigTaxas() {
    fetch('/config/taxas')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            const elements = {
                energyPrice: getElement('energy-price'),
                taxaLixo: getElement('taxa-lixo'),
                taxaRadio: getElement('taxa-radio'),
                ivaPercent: getElement('iva-percent')
            };

            if (elements.energyPrice && data.preco_kwh !== undefined)
                elements.energyPrice.value = data.preco_kwh;
            if (elements.taxaLixo && data.taxa_lixo !== undefined)
                elements.taxaLixo.value = data.taxa_lixo;
            if (elements.taxaRadio && data.taxa_radio !== undefined)
                elements.taxaRadio.value = data.taxa_radio;
            if (elements.ivaPercent && data.iva_percent !== undefined)
                elements.ivaPercent.value = data.iva_percent;
        })
        .catch(error => {
            console.error('Erro ao carregar taxas:', error);
        });
}

// 🔹 Salvar configurações de taxas
function salvarConfigTaxas() {
    const elements = {
        energyPrice: getElement('energy-price'),
        taxaLixo: getElement('taxa-lixo'),
        taxaRadio: getElement('taxa-radio'),
        ivaPercent: getElement('iva-percent')
    };

    if (Object.values(elements).some(el => !el)) return;

    const taxas = {
        preco_kwh: parseFloat(elements.energyPrice.value),
        taxa_lixo: parseFloat(elements.taxaLixo.value),
        taxa_radio: parseFloat(elements.taxaRadio.value),
        iva_percent: parseFloat(elements.ivaPercent.value)
    };

    // Validações
    if (taxas.preco_kwh <= 0 || taxas.preco_kwh > 10) {
        showToast('O preço por kWh deve ser entre 0.1 e 10 MZN', 'warning');
        return;
    }
    if (taxas.taxa_lixo < 0 || taxas.taxa_lixo > 20) {
        showToast('A taxa de lixo deve ser entre 0 e 20 MZN', 'warning');
        return;
    }
    if (taxas.taxa_radio < 0 || taxas.taxa_radio > 20) {
        showToast('A taxa de rádio deve ser entre 0 e 20 MZN', 'warning');
        return;
    }
    if (taxas.iva_percent < 0 || taxas.iva_percent > 30) {
        showToast('O IVA deve ser entre 0 e 30%', 'warning');
        return;
    }

    fetch('/config/taxas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taxas)
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('Taxas salvas com sucesso!', 'success');
            atualizarInfoSaldoConfig(); // Atualizar saldo com novo preço
        } else {
            showToast(`Erro ao salvar taxas: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erro ao salvar taxas:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    });
}

// 🔹 Calcular recarga
function calcularRecargaConfig() {
    const valorRecargaInput = getElement('valor-recarga');
    if (!valorRecargaInput) return;

    const valorMzn = valorRecargaInput.value.trim();
    
    if (!valorMzn || valorMzn <= 0) {
        showToast('Por favor, insira um valor válido em MZN', 'warning');
        return;
    }

    fetch('/recargas/calcular', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ valor_mzn: parseFloat(valorMzn) })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const resultado = data.resultado;
            mostrarDetalhesRecarga(resultado);
            showToast('Cálculo realizado com sucesso!', 'success');
        } else {
            showToast(`Erro ao calcular: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erro ao calcular recarga:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    });
}

// 🔹 Mostrar detalhes da recarga calculada
function mostrarDetalhesRecarga(resultado) {
    const elements = {
        detalhesRecarga: getElement('detalhes-recarga'),
        btnConfirmar: getElement('btn-confirmar-recarga'),
        kwhCreditar: getElement('kwh-a-creditar'),
        detValorBruto: getElement('det-valor-bruto'),
        detTaxaLixo: getElement('det-taxa-lixo'),
        detTaxaRadio: getElement('det-taxa-radio'),
        detIvaPercent: getElement('det-iva-percent'),
        detValorIva: getElement('det-valor-iva'),
        detValorLiquido: getElement('det-valor-liquido'),
        detKwhCreditar: getElement('det-kwh-creditar')
    };

    if (Object.values(elements).some(el => !el)) return;

    // Atualizar valores
    elements.detValorBruto.textContent = resultado.valor_mzn;
    elements.detTaxaLixo.textContent = resultado.taxa_lixo;
    elements.detTaxaRadio.textContent = resultado.taxa_radio;
    elements.detIvaPercent.textContent = resultado.iva_percent;
    elements.detValorIva.textContent = (resultado.valor_liquido - resultado.valor_com_iva).toFixed(2);
    elements.detValorLiquido.textContent = resultado.valor_com_iva;
    elements.detKwhCreditar.textContent = resultado.kwh_creditados;
    elements.kwhCreditar.textContent = resultado.kwh_creditados;

    // Mostrar elementos
    elements.detalhesRecarga.style.display = 'block';
    elements.btnConfirmar.style.display = 'block';
}

// 🔹 Confirmar recarga
function confirmarRecargaConfig() {
    const valorRecargaInput = getElement('valor-recarga');
    if (!valorRecargaInput) return;

    const valorMzn = valorRecargaInput.value.trim();
    
    if (!valorMzn || valorMzn <= 0) {
        showToast('Por favor, insira um valor válido em MZN', 'warning');
        return;
    }

    fetch('/recargas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ valor_mzn: parseFloat(valorMzn) })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            limparFormularioRecarga();
            atualizarInfoSaldoConfig();
        } else {
            showToast(`Erro: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erro ao confirmar recarga:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    });
}

// 🔹 Limpar formulário de recarga
function limparFormularioRecarga() {
    const elements = {
        valorRecarga: getElement('valor-recarga'),
        detalhesRecarga: getElement('detalhes-recarga'),
        btnConfirmar: getElement('btn-confirmar-recarga')
    };

    if (elements.valorRecarga) elements.valorRecarga.value = '';
    if (elements.detalhesRecarga) elements.detalhesRecarga.style.display = 'none';
    if (elements.btnConfirmar) elements.btnConfirmar.style.display = 'none';
}

// 🔹 Atualizar informações do saldo na configuração
function atualizarInfoSaldoConfig() {
    fetch('/saldo/info')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                const elements = {
                    saldoKwh: getElement('saldoKwhConfig'),
                    saldoMzn: getElement('saldoMznConfig'),
                    previsao: getElement('previsaoConfig')
                };

                if (elements.saldoKwh) elements.saldoKwh.textContent = data.saldo_kwh;
                if (elements.saldoMzn) elements.saldoMzn.textContent = data.valor_restante_mzn;
                
                if (elements.previsao && data.previsao && data.previsao !== "Indeterminado") {
                    elements.previsao.textContent = 
                        `${data.previsao.dias_restantes} dias (até ${data.previsao.data_termino})`;
                } else if (elements.previsao) {
                    elements.previsao.textContent = 'Indeterminado';
                }
            }
        })
        .catch(error => {
            console.error('Erro ao atualizar saldo:', error);
        });
}

// 🔹 Mostrar histórico de recargas
function mostrarHistoricoRecargas() {
    fetch('/recargas')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            const contentDiv = getElement('historico-recargas-content');
            if (!contentDiv) return;

            if (data.success && data.recargas.length > 0) {
                let html = `
                    <div class="table-responsive">
                        <table class="table table-sm table-striped">
                            <thead>
                                <tr>
                                    <th>Data</th>
                                    <th>Valor MZN</th>
                                    <th>KWh Creditados</th>
                                    <th>Saldo Anterior</th>
                                    <th>Saldo Actual</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                data.recargas.forEach(recarga => {
                    html += `
                        <tr>
                            <td>${recarga.criado_em}</td>
                            <td>${recarga.valor_mzn} MZN</td>
                            <td>${recarga.kwh_creditados} kWh</td>
                            <td>${recarga.saldo_anterior} kWh</td>
                            <td>${recarga.saldo_atual} kWh</td>
                        </tr>
                    `;
                });
                
                html += `
                            </tbody>
                        </table>
                    </div>
                    <div class="mt-2 text-muted">
                        Total de recargas: ${data.total}
                    </div>
                `;
                
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = '<p class="text-center text-muted">Nenhuma recarga encontrada.</p>';
            }
            
            // Mostrar modal (usando Bootstrap)
            const historicoModal = new bootstrap.Modal(document.getElementById('historicoModal'));
            historicoModal.show();
        })
        .catch(error => {
            console.error('Erro ao carregar histórico:', error);
        });
}
// Salvar configuração de preço
function carregarConfigPreco() {
    const priceInput = getElement('energy-price');
    if (!priceInput) return;

    fetch('/config/preco')
        .then(response => {
            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.preco_kwh !== undefined) {
                priceInput.value = data.preco_kwh;
            }
        })
        .catch(error => {
            console.error('Erro ao carregar preço:', error);
        });
}
function salvarConfigPreco() {
    const priceInput = getElement('energy-price');
    if (!priceInput) return;

    const preco = parseFloat(priceInput.value);
    if (isNaN(preco) || preco <= 0 || preco > 16) {
        showToast('O preço por kWh deve ser um número entre 0.1 e 16', 'warning');
        return;
    }

    fetch('/config/preco', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preco_kwh: preco })  
        
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast('Preço da energia salvo com sucesso!', 'success');
            atualizarDashboard();
        } else {
            showToast(`Erro ao salvar preço: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Erro ao salvar preço:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
    });
}

// Gerar relatório
function gerarRelatorio() {
    const elements = {
        reportType: getElement('report-type'),
        reportPeriod: getElement('report-period'),
        reportPzem: getElement('report-pzem'),
        startDate: getElement('start-date'),
        endDate: getElement('end-date'),
        reportResults: getElement('report-results')
    };

    if (Object.values(elements).some(el => !el && el !== elements.startDate && el !== elements.endDate)) return;

    const reportType = elements.reportType.value;
    const reportPeriod = elements.reportPeriod.value;
    const reportPzem = elements.reportPzem.value;
    let startDate = elements.startDate?.value;
    let endDate = elements.endDate?.value;

    if (reportPeriod === 'custom') {
        if (!startDate || !endDate) {
            showToast('Por favor, selecione as datas inicial e final', 'warning');
            return;
        }
        if (new Date(startDate) > new Date(endDate)) {
            showToast('A data inicial não pode ser posterior à data final', 'warning');
            return;
        }
    }

    fetch('/api/relatorio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: reportType,
            period: reportPeriod,
            pzem: reportPzem,
            startDate,
            endDate
        })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success && data.dados) {
            showToast('Relatório gerado com sucesso!', 'success');
            const reportResults = elements.reportResults;
            reportResults.innerHTML = '';

            // Renderizar tabela de resultados
            const table = document.createElement('table');
            table.className = 'table table-hover reles-table';
            table.innerHTML = `
                <thead>
                    <tr>
                        ${reportType === 'consumo' ? '<th>Data</th><th>Energia (kWh)</th><th>Custo (MZN)</th>' :
                          reportType === 'picos' ? '<th>Data</th><th>Pico (W)</th><th>Hora</th>' :
                          reportType === 'reles' ? '<th>Relé</th><th>PZEM</th><th>Consumo (W)</th><th>Estado</th>' :
                          '<th>Data</th><th>Custo (MZN)</th><th>Energia (kWh)</th>'}
                    </tr>
                </thead>
                <tbody>
                    ${data.dados.map(row => `
                        <tr>
                            ${reportType === 'consumo' ? `
                                <td>${row.data}</td>
                                <td>${row.energia.toFixed(3)}</td>
                                <td>${row.custo.toFixed(2)}</td>
                            ` : reportType === 'picos' ? `
                                <td>${row.data}</td>
                                <td>${row.pico.toFixed(1)}</td>
                                <td>${row.hora}</td>
                            ` : reportType === 'reles' ? `
                                <td>${row.nome}</td>
                                <td>PZEM ${row.pzem_id}</td>
                                <td>${row.consumo.toFixed(1)}</td>
                                <td><span class="badge ${row.estado ? 'bg-success' : 'bg-secondary'}">${row.estado ? 'Ligado' : 'Desligado'}</span></td>
                            ` : `
                                <td>${row.data}</td>
                                <td>${row.custo.toFixed(2)}</td>
                                <td>${row.energia.toFixed(3)}</td>
                            `}
                        </tr>
                    `).join('')}
                </tbody>
            `;
            reportResults.appendChild(table);
        } else {
            showToast(`Erro ao gerar relatório: ${data.message}`, 'danger');
            elements.reportResults.innerHTML = `
                <p class="text-muted text-center py-5">
                    Erro ao gerar relatório: ${data.message}
                </p>
            `;
        }
    })
    .catch(error => {
        console.error('Erro ao gerar relatório:', error);
        showToast('Erro de comunicação com o servidor', 'danger');
        elements.reportResults.innerHTML = `
            <p class="text-muted text-center py-5">
                Erro ao carregar relatório. Tente novamente.
            </p>
        `;
    });
}

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    inicializarSistemaAlertas();
    inicializarGraficos();
    atualizarDashboard();
    carregarReles();
    carregarConfigLimites();
    carregarConfigNotificacoes();
    carregarConfigPreco();
    carregarConfigTaxas(); // ← ADICIONE ESTA LINHA
    carregarModosReles();
    atualizarInfoSaldoConfig();
    setInterval(atualizarDashboard, 5000);
   

    const elements = {
        reportPeriod: getElement('report-period'),
        reportForm: getElement('report-form'),
        limitConfigForm: getElement('limit-config-form'),
        priceConfigForm: getElement('price-config-form'),
        notificationConfigForm: getElement('notification-config-form'),
        addReleForm: getElement('add-rele-form'),
        editReleForm: getElement('edit-rele-form'),
        taxConfigForm: getElement('price-tax-config-form'),
        searchReles: getElement('search-reles'),
        filterPzem: getElement('filter-pzem')
    };


    if (elements.reportPeriod) {
        elements.reportPeriod.addEventListener('change', function() {
            const customDates = getElement('custom-dates');
            if (customDates) customDates.style.display = this.value === 'custom' ? 'block' : 'none';
        });
    }

    if (elements.reportForm) {
        elements.reportForm.addEventListener('submit', function(e) {
            e.preventDefault();
            gerarRelatorio();
        });
    }

    if (elements.limitConfigForm) {
        elements.limitConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarConfigLimites();
        });
    }
        // 🔹 Salvar preço por kWh
    if (elements.priceConfigForm) {
        elements.priceConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarConfigPreco();
        });
    }

    // 🔹 Salvar taxas (lixo, rádio, IVA)
    if (elements.taxConfigForm) {
        elements.taxConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarConfigTaxas();
        });
    }

    if (elements.notificationConfigForm) {
        elements.notificationConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarConfigNotificacoes();
        });
    }

    if (elements.addReleForm) {
        elements.addReleForm.addEventListener('submit', function(e) {
            e.preventDefault();
            addRele();
        });
    }

    if (elements.editReleForm) {
        elements.editReleForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarEdicaoRele();
        });
    }

    if (elements.searchReles) {
        elements.searchReles.addEventListener('keyup', debounce(filtrarReles, 300));
    }

    if (elements.filterPzem) {
        elements.filterPzem.addEventListener('change', filtrarReles);
    }
    
        // Atualizar saldo automaticamente quando na aba de configurações
    setInterval(() => {
        const configuracoesTab = getElement('configuracoes');
        if (configuracoesTab && configuracoesTab.classList.contains('active')) {
            atualizarInfoSaldoConfig();
        }
    }, 30000);
});
