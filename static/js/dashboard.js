
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

function resetarKPISelecionado() {
    const select = document.getElementById("select-reset-kpi");
    const id = select.value;

    if (!id) {
        showToast("Selecione um KPI para resetar!", "warning");
        return;
    }

    if (id === "reset-all") {
        resetarTodosKPIs();
        showToast("Todos os KPIs foram zerados!", "success");
        return;
    }

    const el = document.getElementById(id);

    if (el) {
        el.innerText = "0";
        showToast(`KPI "${select.options[select.selectedIndex].text}" foi zerado!`, "success");
    } else {
        showToast("Erro: KPI não encontrado!", "danger");
    }
}

function resetarTodosKPIs() {
    const ids = [
        "kpi-current-power",
        "kpi-today-energy",
        "kpi-today-cost",
        "kpi-peak-today",
        "kpi-peak-time",
        "kpi-savings",
        "kpi-peak-weekly",
        "kpi-peak-weekly-time",
        "kpi-peak-monthly",
        "kpi-peak-monthly-time"
    ];

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = "0";
    });
}

// Atualizar KPIs
async function atualizarKPIs(data) {
    const elements = {
        currentPower: getElement('kpi-current-power'),
        todayEnergy: getElement('kpi-today-energy'),
        todayCost: getElement('kpi-today-cost'),
        peakToday: getElement('kpi-peak-today'),
        peakTime: getElement('kpi-peak-time'),
        savings: getElement('kpi-savings'),
        // ✅ NOVOS: Picos semanal e mensal
        peakWeekly: getElement('kpi-peak-weekly'),
        peakWeeklyTime: getElement('kpi-peak-weekly-time'),
        peakMonthly: getElement('kpi-peak-monthly'),
        peakMonthlyTime: getElement('kpi-peak-monthly-time')
    };

    if (Object.values(elements).some(el => !el)) return;

    const totalPower = data.pzem1.power + data.pzem2.power;
    
    // ✅ CORREÇÃO: Usar energia atual (saldo) em vez de energia consumida
    const energiaAtual = data.energia_atual?.saldo_kwh || 0;
    const valorEnergiaAtual = data.energia_atual?.valor_mzn || 0;
    
    // ✅ CORREÇÃO: Picos agora vêm do banco de dados
    const picoHoje = data.peak_today?.value || 0;
    const horaPico = data.peak_today?.time || '--:--';
    
    // ✅ NOVOS: Picos semanal e mensal
    const picoSemanal = data.peak_weekly?.value || 0;
    const horaPicoSemanal = data.peak_weekly?.time || '--:--';
    const picoMensal = data.peak_monthly?.value || 0;
    const horaPicoMensal = data.peak_monthly?.time || '--:--';

    // Atualizar elementos existentes
    elements.currentPower.textContent = totalPower.toFixed(1) + ' W';
    elements.todayEnergy.textContent = energiaAtual.toFixed(2) + ' kWh';
    elements.todayCost.textContent = `MZN ${valorEnergiaAtual.toFixed(2)}`;
    elements.peakToday.textContent = picoHoje.toFixed(1) + ' W';
    elements.peakTime.textContent = horaPico;
    
    // ✅ NOVOS: Atualizar picos semanal e mensal
    if (elements.peakWeekly) {
        elements.peakWeekly.textContent = picoSemanal.toFixed(1) + ' W';
    }
    if (elements.peakWeeklyTime) {
        elements.peakWeeklyTime.textContent = horaPicoSemanal;
    }
    if (elements.peakMonthly) {
        elements.peakMonthly.textContent = picoMensal.toFixed(1) + ' W';
    }
    if (elements.peakMonthlyTime) {
        elements.peakMonthlyTime.textContent = horaPicoMensal;
    }
    
    // ✅ CORREÇÃO: Substituir "Economia" por "Saldo de Energia"
    elements.savings.textContent = energiaAtual.toFixed(0) + '%';
    
    // ✅ Atualizar também o tooltip ou texto explicativo se necessário
    const savingsElement = getElement('kpi-savings');
    if (savingsElement) {
        savingsElement.title = "Saldo de Energia Disponível";
    }
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
        // ✅ AGORA: Gráfico mostra picos de cada dia da semana atual
        state.charts.peakChart.data.labels = data.peaks.labels;
        state.charts.peakChart.data.datasets[0].data = data.peaks.values;
        state.charts.peakChart.update();
        
        // ✅ Atualizar título do gráfico
        state.charts.peakChart.options.plugins.title.text = 'Picos de Consumo - Esta Semana';
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
//LDR
async function atualizarLDR() {
    try {
        const resp = await fetch("/api/get_ldr");
        const data = await resp.json();

        if (!data.success) return;

        // Atualizar luminosidade
        document.getElementById("r1-luz").innerText = data.valorLuz;

        // Elementos visuais
        const card = document.getElementById("card-r1");
        const estadoTexto = document.getElementById("r1-estado-texto");

        if (data.R1 == 1) {
            estadoTexto.innerText = "LIGADO";

            card.classList.remove("stat-off");
            card.classList.add("stat-on");
        } else {
            estadoTexto.innerText = "DESLIGADO";

            card.classList.remove("stat-on");
            card.classList.add("stat-off");
        }

    } catch (e) {
        console.log("Erro ao buscar LDR:", e);
    }
}
 


// Atualizar KPIs
async function atualizarKPIs(data) {
    const elements = {
        currentPower: getElement('kpi-current-power'),
        todayEnergy: getElement('kpi-today-energy'),
        todayCost: getElement('kpi-today-cost'),
        peakToday: getElement('kpi-peak-today'),
        peakTime: getElement('kpi-peak-time'),
        savings: getElement('kpi-savings'),
        // ✅ NOVOS: Picos semanal e mensal
        peakWeekly: getElement('kpi-peak-weekly'),
        peakWeeklyTime: getElement('kpi-peak-weekly-time'),
        peakMonthly: getElement('kpi-peak-monthly'),
        peakMonthlyTime: getElement('kpi-peak-monthly-time')
    };

    if (Object.values(elements).some(el => !el)) return;

    const totalPower = data.pzem1.power + data.pzem2.power;
    
    // ✅ CORREÇÃO: Usar energia atual (saldo) em vez de energia consumida
    const energiaAtual = data.energia_atual?.saldo_kwh || 0;
    const valorEnergiaAtual = data.energia_atual?.valor_mzn || 0;
    
    // ✅ CORREÇÃO: Picos agora vêm do banco de dados
    const picoHoje = data.peak_today?.value || 0;
    const horaPico = data.peak_today?.time || '--:--';
    
    // ✅ NOVOS: Picos semanal e mensal
    const picoSemanal = data.peak_weekly?.value || 0;
    const horaPicoSemanal = data.peak_weekly?.time || '--:--';
    const picoMensal = data.peak_monthly?.value || 0;
    const horaPicoMensal = data.peak_monthly?.time || '--:--';

    // Atualizar elementos existentes
    elements.currentPower.textContent = totalPower.toFixed(1) + ' W';
    elements.todayEnergy.textContent = energiaAtual.toFixed(2) + ' kWh';
    elements.todayCost.textContent = `MZN ${valorEnergiaAtual.toFixed(2)}`;
    elements.peakToday.textContent = picoHoje.toFixed(1) + ' W';
    elements.peakTime.textContent = horaPico;
    
    // ✅ NOVOS: Atualizar picos semanal e mensal
    if (elements.peakWeekly) {
        elements.peakWeekly.textContent = picoSemanal.toFixed(1) + ' W';
    }
    if (elements.peakWeeklyTime) {
        elements.peakWeeklyTime.textContent = horaPicoSemanal;
    }
    if (elements.peakMonthly) {
        elements.peakMonthly.textContent = picoMensal.toFixed(1) + ' W';
    }
    if (elements.peakMonthlyTime) {
        elements.peakMonthlyTime.textContent = horaPicoMensal;
    }
    
    // ✅ CORREÇÃO: Substituir "Economia" por "Saldo de Energia"
    elements.savings.textContent = energiaAtual.toFixed(0) + '%';
    
    // ✅ Atualizar também o tooltip ou texto explicativo se necessário
    const savingsElement = getElement('kpi-savings');
    if (savingsElement) {
        savingsElement.title = "Saldo de Energia Disponível";
    }
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
        // ✅ AGORA: Gráfico mostra picos de cada dia da semana atual
        state.charts.peakChart.data.labels = data.peaks.labels;
        state.charts.peakChart.data.datasets[0].data = data.peaks.values;
        state.charts.peakChart.update();
        
        // ✅ Atualizar título do gráfico
        state.charts.peakChart.options.plugins.title.text = 'Picos de Consumo - Esta Semana';
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

async function alterarModo(releId, modoAtual) {
    try {
        const resp = await fetch(`/api/reles/${releId}/modo`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ modo_automatico: !modoAtual })
        });

        const data = await resp.json();

        if (data.success) {
            showToast(data.message, "info");
        } else {
            showToast(`Erro: ${data.error}`, "danger");
        }

        await carregarReles();

    } catch (e) {
        console.error(e);
        showToast("Erro ao alterar modo", "danger");
    }
}

// Alternar estado (apenas modo Manual) - VERSÃO CORRIGIDA
async function alternarEstadoRele(releId) {
    try {
        const resp = await fetch(`/api/reles/${releId}/toggle-state`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });

        const data = await resp.json();

        if (data.success) {
            showToast(data.message, "success");
        } else {
            showToast(`Erro: ${data.error}`, "danger");
        }

        await carregarReles();

    } catch (e) {
        console.error(e);
        showToast("Erro ao enviar comando manual", "danger");
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
    try {
        const resp = await fetch("/api/reles");
        const data = await resp.json();

        if (!data.success) {
            showToast("Erro ao carregar relés", "danger");
            return;
        }

        const tabela = document.getElementById("tabela-reles");
        tabela.innerHTML = "";

        data.reles.forEach(rele => {
            const linha = document.createElement("tr");

            // Estado visual
            const badgeEstado = rele.estado
                ? '<span class="badge bg-success">Ligado</span>'
                : '<span class="badge bg-secondary">Desligado</span>';

            // Modo visual
            const badgeModo = rele.modo_automatico
                ? '<span class="badge bg-primary">Automático</span>'
                : '<span class="badge bg-warning text-dark">Manual</span>';

            // Botão de modo
            const btnModo = `
                <button class="btn btn-sm btn-outline-primary"
                    onclick="alterarModo(${rele.id}, ${rele.modo_automatico})">
                    ${rele.modo_automatico ? "Automático" : "Manual"}
                </button>
            `;

            // Botão de ligar/desligar — SOMENTE MANUAL
            const btnPower = !rele.modo_automatico
                ? `
                <button class="btn btn-sm ${rele.estado ? "btn-danger" : "btn-success"}"
                    onclick="alternarEstadoRele(${rele.id})">
                    ${rele.estado ? "Desligar" : "Ligar"}
                </button>`
                : `
                <button class="btn btn-sm btn-secondary" disabled>
                    Automático
                </button>`;

            linha.innerHTML = `
                <td>${rele.id}</td>
                <td>${rele.nome}</td>
                <td>${badgeEstado}</td>
                <td>${badgeModo}</td>
                <td>${btnModo}</td>
                <td>${btnPower}</td>
            `;

            tabela.appendChild(linha);
        });

    } catch (e) {
        console.error(e);
        showToast("Erro ao atualizar interface", "danger");
    }
}
async function iniciarDashboard() {
    await carregarReles();

    // Atualiza a cada 5 segundos
    setInterval(async () => {
        await carregarReles();
    }, 5000);
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

            <td>${typeof rele.limite_individual !== 'undefined' ? rele.limite_individual : 0} kWh</td>
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

    // 🔹 Elementos do formulário
    const elements = {
        id: getElement('edit-rele-id'),
        name: getElement('edit-rele-name'),
        pzem: getElement('edit-rele-pzem'),
        limit: getElement('edit-rele-limit'),
        priority: getElement('edit-rele-priority'),
        mode: getElement('edit-rele-mode')
    };

    // 🔹 Verificação de existência
    const missing = Object.keys(elements).filter(k => !elements[k]);
    if (missing.length > 0) {
        showToast(`Erro: Elementos ausentes: ${missing.join(', ')}`, "danger");
        return;
    }

    // 🔹 Preparar dados
    const releId = elements.id.value;
    const nome = elements.name.value.trim();
    const pzemId = parseInt(elements.pzem.value);
    const limite = parseInt(elements.limit.value);
    const prioridade = parseInt(elements.priority.value);
    const modoAutomatico = elements.mode.value === "auto";

    // 🔹 Validações
    if (!nome || nome.length < 2) {
        showToast("O nome deve ter pelo menos 2 caracteres.", "warning");
        return;
    }

    if (isNaN(pzemId) || pzemId < 1 || pzemId > 2) {
        showToast("Selecione um PZEM válido.", "warning");
        return;
    }

    if (isNaN(limite) || limite <= 0 || limite > 2000) {
        showToast("O limite deve ser entre 1 e 2000 W.", "warning");
        return;
    }

    if (isNaN(prioridade) || prioridade < 1 || prioridade > 5) {
        showToast("A prioridade deve ser entre 1 e 5.", "warning");
        return;
    }

    // 🔹 Verificar duplicidade de nome
    const nomeDuplicado = state.reles.allReles.find(r =>
        r.id !== parseInt(releId) &&
        r.nome.toLowerCase() === nome.toLowerCase()
    );
    if (nomeDuplicado) {
        showToast(`Já existe outro relé com o nome "${nome}"`, "warning");
        return;
    }

    // 🔹 Dados corretos que o BACKEND espera
    const dados = {
        nome: nome,
        pzem_id: pzemId,
        limite_individual: limite,       // ✔ CORRIGIDO!
        prioridade: prioridade,
        modo_automatico: modoAutomatico  // true/false (backend aceita)
    };

    console.log("📤 Atualizando relé:", dados);

    // 🔹 Mostrar loading
    const submitBtn = document.querySelector('#editReleModal button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
    submitBtn.disabled = true;

    try {

        const resp = await fetch(`/api/reles/${releId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(dados)
        });

        const raw = await resp.text();
        let data;

        try {
            data = raw ? JSON.parse(raw) : {};
        } catch {
            console.warn("⚠ Resposta não-JSON:", raw);
            if (resp.ok) data = { success: true };
        }

        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.message || "Erro ao atualizar relé");
        }

        // 🔹 Fechar modal
        const modal = bootstrap.Modal.getInstance(getElement("editReleModal"));
        if (modal) modal.hide();

        showToast("Relé atualizado com sucesso!", "success");

        // 🔹 Recarregar
        await Promise.all([carregarReles(), carregarModosReles()]);

        console.log("✔ Relé atualizado:", dados);

    } catch (error) {
        console.error("❌ Erro ao salvar edição:", error);
        showToast(`Erro: ${error.message}`, "danger");

    } finally {
        // 🔹 Restaurar botão
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
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
async function addRele(event) {
    if (event) event.preventDefault(); // Previne submit duplo
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
        let originalText = '';
        if (submitBtn) {
            originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Adicionando...';
            submitBtn.disabled = true;
        }

        const response = await fetch('/api/reles', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                nome: nome,
                pzem_id: pzemId,
                limite_individual: limite,
                prioridade: prioridade,
                modo_automatico: modoAutomatico, // ✅ Campo de modo
                estado: false, // Inicia desligado por padrão
                consumo_atual: 0 // Consumo inicial zero
            })
        });

        // Restaurar botão
        if (submitBtn) {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Fechar modal e resetar formulário
            const modal = bootstrap.Modal.getInstance(getElement('addReleModal'));
            if (modal) modal.hide();

            elements.form.reset();

            showToast('Relé adicionado com sucesso!', 'success');

            // Atualizar dados
            await Promise.all([
                carregarReles(),
                carregarModosReles() // Atualizar modos
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

// Adiciona o event listener para o formulário de adicionar relé
const addReleForm = document.getElementById('add-rele-form');
if (addReleForm) {
    addReleForm.addEventListener('submit', addRele);
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

// =====================================================
// GERADOR DE RELATÓRIOS
// =====================================================

document.getElementById("report-form").addEventListener("submit", function(e) {
    e.preventDefault();
    gerarRelatorio();
});

function gerarRelatorio() {
    const type = document.getElementById("report-type").value;
    const period = document.getElementById("report-period").value;
    const pzem = document.getElementById("report-pzem").value;

    let startDate = document.getElementById("start-date").value;
    let endDate = document.getElementById("end-date").value;

    // Validação para período customizado
    if (period === "custom") {
        if (!startDate || !endDate) {
            showToast("Selecione o intervalo de datas!", "warning");
            return;
        }
        
        // Validar se data final é maior que data inicial
        if (new Date(endDate) < new Date(startDate)) {
            showToast("Data final deve ser maior que data inicial!", "warning");
            return;
        }
    }

    // Mostrar estado de carregamento
    const resultsContainer = document.getElementById('report-results');
    resultsContainer.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-2 text-muted">Gerando relatório...</p>
        </div>
    `;

    // Desabilitar botão para evitar múltiplos cliques
    const submitBtn = document.querySelector('#report-form button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Gerando...';
    submitBtn.disabled = true;

    fetch("/api/relatorio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            type,
            period,
            pzem,
            startDate,
            endDate
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        return response.json();
    })
    .then(res => {
        if (!res.success) {
            showToast(res.message || "Erro ao processar relatório", "danger");
            resultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h6><i class="bi bi-exclamation-triangle"></i> Erro no Relatório</h6>
                    <p class="mb-0">${res.message || "Erro desconhecido"}</p>
                    ${res.details ? `<small class="text-muted">Detalhes: ${res.details}</small>` : ''}
                </div>
            `;
            return;
        }
        
        // Armazena dados para exportação
        setReportData(res); 
        
        // Renderiza a tabela do relatório
        renderReportTable(type, res.dados, res.metadata);
        
        // Mostra mensagem de sucesso
        showToast(`Relatório gerado com ${res.dados?.length || 0} registros`, "success");
    })
    .catch(error => {
        console.error('Erro ao gerar relatório:', error);
        
        let errorMessage = "Erro ao gerar relatório!";
        if (error.message.includes('Failed to fetch')) {
            errorMessage = "Erro de conexão com o servidor. Verifique sua internet.";
        } else if (error.message.includes('HTTP')) {
            errorMessage = "Erro no servidor. Tente novamente.";
        }
        
        showToast(errorMessage, "danger");
        
        resultsContainer.innerHTML = `
            <div class="alert alert-danger">
                <h6><i class="bi bi-exclamation-triangle"></i> Erro de Conexão</h6>
                <p class="mb-0">${errorMessage}</p>
                <small class="text-muted">Detalhes: ${error.message}</small>
            </div>
        `;
    })
    .finally(() => {
        // Restaurar botão
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

// Função auxiliar para renderizar tabela de relés com os novos campos
function renderReportTable(type, dados, metadata) {
    const container = document.getElementById('report-results');
    
    if (!dados || dados.length === 0) {
        container.innerHTML = `
            <div class="estado-vazio">
                <i class="bi bi-inbox"></i>
                <h6>Nenhum dado encontrado</h6>
                <p class="text-muted">Não foram encontrados registros para os filtros selecionados.</p>
            </div>
        `;
        return;
    }

    switch(type) {
        case 'reles':
            renderRelatorioReles(dados, metadata);
            break;
        case 'consumo':
            renderRelatorioConsumo(dados, metadata);
            break;
        case 'picos':
            renderRelatorioPicos(dados, metadata);
            break;
        case 'custo':
            renderRelatorioCusto(dados, metadata);
            break;
        case 'recargas':
            renderRelatorioRecargas(dados, metadata);
            break;
        default:
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    Tipo de relatório não implementado: ${type}
                </div>
            `;
    }
}

// Função específica para relatório de relés com os novos campos
function renderRelatorioReles(dados, metadata) {
    const container = document.getElementById('report-results');
    
    let html = `
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h6><i class="bi bi-cpu"></i> Desempenho por Relé</h6>
            <span class="badge bg-primary">${metadata?.periodo || 'Período'}</span>
        </div>
        
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Relé</th>
                        <th>PZEM</th>
                        <th>Estado</th>
                        <th>Modo</th>
                        <th>Consumo Médio</th>
                        <th>Tempo Ligado</th>
                        <th>Tempo Desligado</th>
                        <th>Ciclos</th>
                        <th>Eficiência</th>
                    </tr>
                </thead>
                <tbody>
    `;

    dados.forEach(rele => {
        // 🔥 CORREÇÃO: Garantir que todos os valores existam
        const nome = rele.nome || "Sem nome";
        const pzem_id = rele.pzem_id || 1;
        const estado = rele.estado || "DESLIGADO";
        const modo = rele.modo || "Manual";
        const consumo_medio = typeof rele.consumo_medio === 'number' ? rele.consumo_medio : 0;
        const tempo_ligado = rele.tempo_ligado || "0.0h";
        const tempo_desligado = rele.tempo_desligado || "0.0h";
        const ciclos = rele.ciclos || rele.mudancas_estado || 0;
        
        // 🔥 CORREÇÃO CRÍTICA: Tratar eficiencia_tempo que pode ser undefined
        let eficiencia_tempo = "0%";
        let eficiencia_valor = 0;
        
        if (rele.eficiencia_tempo) {
            // Pode ser string "50%" ou número
            if (typeof rele.eficiencia_tempo === 'string') {
                eficiencia_valor = parseFloat(rele.eficiencia_tempo) || 0;
                eficiencia_tempo = rele.eficiencia_tempo;
            } else if (typeof rele.eficiencia_tempo === 'number') {
                eficiencia_valor = rele.eficiencia_tempo;
                eficiencia_tempo = eficiencia_valor.toFixed(1) + '%';
            }
        }

        const estadoClass = estado === 'LIGADO' ? 'success' : 'secondary';
        const modoClass = modo === 'Automático' ? 'info' : 'warning';
        
        html += `
            <tr>
                <td><strong>${nome}</strong></td>
                <td>PZEM ${pzem_id}</td>
                <td><span class="badge bg-${estadoClass}">${estado}</span></td>
                <td><span class="badge bg-${modoClass}">${modo}</span></td>
                <td>${consumo_medio.toFixed(2)} W</td>
                <td><span class="text-success"><i class="bi bi-clock"></i> ${tempo_ligado}</span></td>
                <td><span class="text-secondary"><i class="bi bi-clock"></i> ${tempo_desligado}</span></td>
                <td>${ciclos}</td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="progress flex-grow-1" style="height: 15px;">
                            <div class="progress-bar bg-success" role="progressbar" 
                                 style="width: ${eficiencia_valor}%" 
                                 aria-valuenow="${eficiencia_valor}" 
                                 aria-valuemin="0" aria-valuemax="100">
                            </div>
                        </div>
                        <small class="ms-2">${eficiencia_tempo}</small>
                    </div>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
        
        <div class="mt-3 p-3 bg-light rounded">
            <div class="row">
                <div class="col-md-6">
                    <strong>Período analisado:</strong> ${metadata?.periodo || 'N/A'}<br>
                    <strong>Total de relés:</strong> ${dados.length}
                </div>
                <div class="col-md-6">
                    <strong>Dias analisados:</strong> ${metadata?.dias_analisados || 'N/A'}<br>
                    <strong>Tipo de relatório:</strong> ${metadata?.tipo || 'desempenho_reles'}
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// Adicione também esta função para debug (opcional)
function debugRelatorio() {
    console.log('Dados do relatório atual:', window.currentReportData);
    
    // Teste rápido da API
    fetch('/api/debug/reles-logs')
        .then(r => r.json())
        .then(data => console.log('Debug logs:', data))
        .catch(err => console.error('Debug error:', err));
}

function debugDadosRelatorio() {
    if (window.currentReportData && window.currentReportData.dados) {
        console.log('📊 Dados do relatório atual:', window.currentReportData.dados);
        
        // Verificar cada campo problematico
        window.currentReportData.dados.forEach((rele, index) => {
            console.log(`Relé ${index}:`, {
                nome: rele.nome,
                consumo_medio: rele.consumo_medio,
                tipo_consumo: typeof rele.consumo_medio,
                eficiencia_tempo: rele.eficiencia_tempo,
                tipo_eficiencia: typeof rele.eficiencia_tempo
            });
        });
    } else {
        console.log('❌ Nenhum dado de relatório disponível');
    }
}
// Para usar o debug, adicione no console do navegador: debugRelatorio()

function renderReportTable(type, dados) {
    const container = document.getElementById("report-results");

    if (!dados.length) {
        container.innerHTML = `<p class="text-muted text-center py-5">Sem dados para mostrar.</p>`;
        return;
    }

    let headers = "";
    let rows = "";

    if (type === "consumo") {
        headers = "<th>Data</th><th>Energia (kWh)</th><th>Custo (MZN)</th>";
        rows = dados.map(d => `
            <tr>
                <td>${d.data}</td>
                <td>${d.energia.toFixed(3)}</td>
                <td>${d.custo.toFixed(2)}</td>
            </tr>
        `).join("");
    }

    if (type === "picos") {
        headers = "<th>Data</th><th>Pico (W)</th><th>Hora</th>";
        rows = dados.map(d => `
            <tr>
                <td>${d.data}</td>
                <td>${d.pico.toFixed(1)}</td>
                <td>${d.hora}</td>
            </tr>
        `).join("");
    }

    if (type === "reles") {
        headers = "<th>Relé</th><th>PZEM</th><th>Consumo Médio (W)</th><th>Estado</th>";
        rows = dados.map(d => `
            <tr>
                <td>${d.nome}</td>
                <td>PZEM ${d.pzem_id}</td>
                <td>${d.consumo.toFixed(1)}</td>
                <td>${d.estado ? "Ligado" : "Desligado"}</td>
            </tr>
        `).join("");
    }

    if (type === "custo") {
        headers = "<th>Descrição</th><th>Energia/Informação</th><th>Valor (MZN)</th>";
        rows = dados.map((d, index) => {
            let rowClass = "";
            let isSeparator = d.data.includes("---");
            let isTotal = d.tipo === "total_consumo" || d.tipo === "total_recargas" || d.tipo === "saldo_liquido";
            let isMetrica = d.tipo === "metrica" || d.tipo === "score" || d.tipo === "previsao" || 
                           d.tipo === "projecao" || d.tipo === "saldo_atual" || d.tipo === "consumo_atual" || 
                           d.tipo === "economia";
            
            let energiaDisplay = typeof d.energia === 'number' ? d.energia.toFixed(3) : d.energia;
            let custoDisplay = typeof d.custo_dia === 'number' ? d.custo_dia.toFixed(2) : d.custo_dia;

            // Aplicar estilos baseados no tipo de linha
            if (isSeparator) {
                rowClass = "table-dark fw-bold text-center";
                energiaDisplay = "-";
                custoDisplay = "-";
            } else if (d.tipo === "total_consumo") {
                rowClass = "table-warning fw-bold";
            } else if (d.tipo === "total_recargas") {
                rowClass = "table-success fw-bold";
                custoDisplay = `+${custoDisplay}`;
            } else if (d.tipo === "saldo_liquido") {
                const isPositivo = parseFloat(d.custo_dia) >= 0;
                rowClass = isPositivo ? "table-primary fw-bold" : "table-danger fw-bold";
                custoDisplay = isPositivo ? `+${custoDisplay}` : custoDisplay;
            } else if (d.tipo === "score") {
                // Colorir baseado na categoria
                if (d.energia.includes("🏆")) rowClass = "table-success";
                else if (d.energia.includes("✅")) rowClass = "table-info";
                else if (d.energia.includes("⚠️")) rowClass = "table-warning";
                else if (d.energia.includes("🔴")) rowClass = "table-danger";
            } else if (isMetrica) {
                rowClass = "table-light";
            }

            // Tratamento especial para valores monetários em métricas
            if (isMetrica && typeof d.custo_dia === 'string' && d.custo_dia.includes('MZN')) {
                // Manter como está se já tem MZN
            } else if (isMetrica && d.tipo !== "metrica" && typeof d.custo_dia === 'number') {
                custoDisplay += ' MZN';
            }

            return `
                <tr class="${rowClass}">
                    <td>${d.data}</td>
                    <td>${energiaDisplay}</td>
                    <td>${custoDisplay}</td>
                </tr>
            `;
        }).join("");
    }

        if (type === "recargas") {
        headers = "<th>Data/Hora</th><th>Valor (MZN)</th><th>KWh Creditados</th><th>Taxa Lixo</th><th>Taxa Rádio</th><th>IVA</th><th>Saldo Anterior</th><th>Saldo Actual</th>";
        rows = dados.map(d => `
            <tr>
                <td>${d.criado_em}</td>
                <td>${d.valor_mzn.toFixed(2)} MZN</td>
                <td>${d.kwh_creditados.toFixed(2)} kWh</td>
                <td>${d.taxa_lixo.toFixed(2)} MZN</td>
                <td>${d.taxa_radio.toFixed(2)} MZN</td>
                <td>${d.iva_percent.toFixed(1)}%</td>
                <td>${d.saldo_anterior.toFixed(2)} kWh</td>
                <td>${d.saldo_atual.toFixed(2)} kWh</td>
            </tr>
        `).join("");
    }
    container.innerHTML = `
        <table class="table table-hover">
            <thead><tr>${headers}</tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    inicializarGraficos();
    atualizarDashboard();
    carregarReles();
    carregarConfigLimites();
    carregarModosReles();
    atualizarInfoSaldoConfig();
    atualizarLDR();
    carregarConfigTaxas();
    carregarConfigPreco();
   setInterval(atualizarLDR, 2000);
    setInterval(atualizarDashboard, 5000);

  // iniciarDashboard();
    const elements = {
        reportPeriod: getElement('report-period'),
        reportForm: getElement('report-form'),
        limitConfigForm: getElement('limit-config-form'),
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

    // 🔹 Salvar taxas (lixo, rádio, IVA)
    if (elements.taxConfigForm) {
        elements.taxConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            salvarConfigTaxas();
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


