// ============================================================
// SOMOS EDUCAÇÃO — Flask Report Generator
// Frontend Interactivity
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('report-form');
    const btnSubmit = document.getElementById('btn-submit');
    const btnViewDashboard = document.getElementById('btn-view-dashboard');
    const dashboardContainer = document.getElementById('dashboard-container');
    const mainContainer = document.querySelector('.container');
    const municipioRadios = document.querySelectorAll('input[name="municipio"]');
    const segmentosStatus = document.getElementById('segmentos-status');
    const progressOverlay = document.getElementById('progress-overlay');

    // ---- Verificar segmentos ao selecionar município ----
    municipioRadios.forEach(radio => {
        radio.addEventListener('change', async (e) => {
            const municipio = e.target.value;
            await verificarSegmentos(municipio);
        });
    });

    // ---- Form submission ----
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const municipio = form.querySelector('input[name="municipio"]:checked');
        const tipo = form.querySelector('input[name="tipo_relatorio"]:checked');

        if (!municipio) {
            showToast('Selecione um município', 'error');
            return;
        }

        if (!tipo) {
            showToast('Selecione o tipo de relatório', 'error');
            return;
        }

        // Start loading
        btnSubmit.classList.add('loading');
        btnSubmit.disabled = true;
        showProgress();

        try {
            updateProgressStep(0);

            const formData = new FormData(form);

            // Use fetch to download the PDF
            const response = await fetch('/gerar-relatorio', {
                method: 'POST',
                body: formData
            });

            updateProgressStep(1);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro desconhecido');
            }

            updateProgressStep(2);

            // Get filename from Content-Disposition header
            const disposition = response.headers.get('Content-Disposition');
            let filename = 'relatorio.pdf';
            if (disposition) {
                const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);
                if (match) filename = decodeURIComponent(match[1]);
            }

            // Download the blob
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            updateProgressStep(3);

            setTimeout(() => {
                hideProgress();
                showToast('Relatório gerado com sucesso! 🎉', 'success');
            }, 600);

        } catch (error) {
            hideProgress();
            showToast(error.message || 'Erro ao gerar relatório', 'error');
            console.error('Erro:', error);
        } finally {
            btnSubmit.classList.remove('loading');
            btnSubmit.disabled = false;
        }
    });

    // ---- Verificar segmentos via AJAX ----
    async function verificarSegmentos(municipio) {
        segmentosStatus.classList.remove('visible');

        try {
            const response = await fetch('/verificar-segmentos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ municipio })
            });

            if (!response.ok) throw new Error('Falha ao verificar');

            const data = await response.json();

            // Update UI
            const infantilEl = document.getElementById('seg-infantil');
            const fundamentalEl = document.getElementById('seg-fundamental');

            if (infantilEl) {
                const badge = infantilEl.querySelector('.badge');
                const count = infantilEl.querySelector('.count');
                if (data.infantil) {
                    badge.className = 'badge badge--ok';
                    badge.textContent = '✓ Disponível';
                } else {
                    badge.className = 'badge badge--empty';
                    badge.textContent = '✗ Sem dados';
                }
                count.textContent = `${data.total_infantil.toLocaleString()} registros`;
            }

            if (fundamentalEl) {
                const badge = fundamentalEl.querySelector('.badge');
                const count = fundamentalEl.querySelector('.count');
                if (data.fundamental) {
                    badge.className = 'badge badge--ok';
                    badge.textContent = '✓ Disponível';
                } else {
                    badge.className = 'badge badge--empty';
                    badge.textContent = '✗ Sem dados';
                }
                count.textContent = `${data.total_fundamental.toLocaleString()} registros`;
            }

            segmentosStatus.classList.add('visible');

            // Habilita os botões se houver dados
            if (data.infantil || data.fundamental) {
                btnSubmit.disabled = false;
                btnViewDashboard.disabled = false;
            } else {
                btnSubmit.disabled = true;
                btnViewDashboard.disabled = true;
            }

        } catch (error) {
            console.error('Erro ao verificar segmentos:', error);
            showToast('Erro ao verificar dados do município', 'error');
        }
    }

    // ---- Progress Overlay ----
    function showProgress() {
        progressOverlay.classList.add('visible');
        // Reset all steps
        document.querySelectorAll('.progress-step').forEach(step => {
            step.classList.remove('active', 'done');
        });
    }

    function hideProgress() {
        progressOverlay.classList.remove('visible');
    }

    const stepMessages = [
        'Conectando ao banco de dados...',
        'Coletando dados das avaliações...',
        'Gerando gráficos e PDF...',
        'Preparando download...'
    ];

    function updateProgressStep(index) {
        const steps = document.querySelectorAll('.progress-step');
        const progressText = document.querySelector('.progress-text');

        steps.forEach((step, i) => {
            if (i < index) {
                step.classList.remove('active');
                step.classList.add('done');
                step.querySelector('.step-icon').textContent = '✓';
            } else if (i === index) {
                step.classList.add('active');
                step.classList.remove('done');
                step.querySelector('.step-icon').textContent = '⟳';
            } else {
                step.classList.remove('active', 'done');
                step.querySelector('.step-icon').textContent = '○';
            }
        });

        if (progressText && stepMessages[index]) {
            progressText.textContent = stepMessages[index];
        }
    }

    // ---- Toast Notifications ----
    function showToast(message, type = 'info') {
        // Remove existing toasts
        document.querySelectorAll('.toast').forEach(t => t.remove());

        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;

        const icons = { success: '✅', error: '❌', info: 'ℹ️' };
        toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;

        document.body.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toast.classList.add('visible');
            });
        });

        // Auto dismiss
        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    // ---- View Dashboard Event ----
    btnViewDashboard.addEventListener('click', async () => {
        const municipioInput = form.querySelector('input[name="municipio"]:checked');
        if (!municipioInput) {
            showToast('Selecione um município', 'error');
            return;
        }

        const municipio = municipioInput.value;

        // Start loading status
        btnViewDashboard.classList.add('loading');
        btnViewDashboard.disabled = true;
        showProgress();

        try {
            updateProgressStep(0); // Conectando ao banco

            const response = await fetch('/obter-dados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ municipio })
            });

            updateProgressStep(1); // Coletando dados

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro desconhecido');
            }

            const payload = await response.json();
            updateProgressStep(2); // Processando gráficos

            const { dados, graficos } = payload;

            // ---- 1. Atualizar Título ----
            document.getElementById('dash-municipio').textContent = municipio;

            // ---- 2. Atualizar KPIs ----
            let totalAlunos = 0;
            let totalEscolas = 0;
            let subAlunosTexts = [];

            if (dados.infantil) {
                totalAlunos += dados.infantil.total_alunos;
                totalEscolas = Math.max(totalEscolas, Object.keys(dados.infantil.escolas).length);
                subAlunosTexts.push(`${dados.infantil.total_alunos} Infantil`);
            }
            if (dados.fundamental) {
                totalAlunos += dados.fundamental.total_alunos;
                const todasEscolasSet = new Set([
                    ...Object.keys(dados.infantil?.escolas || {}),
                    ...Object.keys(dados.fundamental?.escolas || {})
                ]);
                totalEscolas = todasEscolasSet.size;
                subAlunosTexts.push(`${dados.fundamental.total_alunos} Fundamental`);
            }

            document.getElementById('kpi-alunos').textContent = totalAlunos.toLocaleString();
            document.getElementById('kpi-alunos-sub').textContent = subAlunosTexts.join(' | ');
            document.getElementById('kpi-escolas').textContent = totalEscolas.toLocaleString();

            const totalProfs = dados.professores ? dados.professores.total_professores : 0;
            document.getElementById('kpi-professores').textContent = totalProfs.toLocaleString();
            document.getElementById('kpi-professores-sub').textContent = `${totalProfs} avaliadores ativos`;

            // Calcular tempo médio global
            let temposSoma = 0;
            let temposContagem = 0;
            if (dados.infantil && dados.infantil.stats) {
                temposSoma += dados.infantil.stats.media * dados.infantil.total_alunos;
                temposContagem += dados.infantil.total_alunos;
            }
            if (dados.fundamental && dados.fundamental.stats) {
                temposSoma += dados.fundamental.stats.media * dados.fundamental.total_alunos;
                temposContagem += dados.fundamental.total_alunos;
            }
            const tempoMedioMinutos = temposContagem > 0 ? (temposSoma / temposContagem) : 0;
            const tempoMedioHoras = tempoMedioMinutos / 60;
            document.getElementById('kpi-tempo').textContent = `${tempoMedioHoras.toFixed(1)}h`;
            document.getElementById('kpi-tempo-sub').textContent = `Média de ${tempoMedioMinutos.toFixed(0)} min por aluno`;

            // ---- 3. Atualizar Imagens dos Gráficos ----
            const updateChartImage = (id, base64Data) => {
                const img = document.getElementById(id);
                if (img) {
                    if (base64Data) {
                        img.src = `data:image/png;base64,${base64Data}`;
                        img.style.display = 'block';
                    } else {
                        img.src = '';
                        img.style.display = 'none';
                    }
                }
            };

            updateChartImage('img-alunos-segmento', graficos.alunos_segmento);
            updateChartImage('img-tempo-medio', graficos.tempo_medio);
            updateChartImage('img-escolas-avaliadas', graficos.escolas_avaliadas);
            updateChartImage('img-histograma-tempos', graficos.histograma_tempos);
            updateChartImage('img-horarios-alunos', graficos.horarios_alunos);
            updateChartImage('img-heatmap-horarios', graficos.heatmap_horarios);
            updateChartImage('img-professores-dedicacao', graficos.professores_dedicacao);
            updateChartImage('img-professores-dispersao', graficos.professores_dispersao);

            // Estágios
            const cardHeatmapInfantil = document.getElementById('card-heatmap-infantil');
            if (graficos.heatmap_estagios_infantil) {
                updateChartImage('img-heatmap-estagios-infantil', graficos.heatmap_estagios_infantil);
                cardHeatmapInfantil.style.display = 'block';
            } else {
                cardHeatmapInfantil.style.display = 'none';
            }

            const cardHeatmapFundamental = document.getElementById('card-heatmap-fundamental');
            if (graficos.heatmap_estagios_fundamental) {
                updateChartImage('img-heatmap-estagios-fundamental', graficos.heatmap_estagios_fundamental);
                cardHeatmapFundamental.style.display = 'block';
            } else {
                cardHeatmapFundamental.style.display = 'none';
            }

            // Outliers
            const cardOutliersInfantil = document.getElementById('card-outliers-infantil');
            if (graficos.outliers_infantil) {
                updateChartImage('img-outliers-infantil', graficos.outliers_infantil);
                cardOutliersInfantil.style.display = 'block';
            } else {
                cardOutliersInfantil.style.display = 'none';
            }

            const cardOutliersFundamental = document.getElementById('card-outliers-fundamental');
            if (graficos.outliers_fundamental) {
                updateChartImage('img-outliers-fundamental', graficos.outliers_fundamental);
                cardOutliersFundamental.style.display = 'block';
            } else {
                cardOutliersFundamental.style.display = 'none';
            }

            // ---- 4. Popular Tabelas ----
            // Tabela 1: Escolas
            const tbodyEscolas = document.querySelector('#table-escolas tbody');
            tbodyEscolas.innerHTML = '';
            
            // Agrupar escolas de ambos os segmentos
            const todasEscolasNomes = new Set([
                ...Object.keys(dados.infantil?.escolas || {}),
                ...Object.keys(dados.fundamental?.escolas || {})
            ]);

            Array.from(todasEscolasNomes).sort().forEach(escola => {
                const infAlunos = dados.infantil?.escolas[escola]?.total_alunos || 0;
                const fundAlunos = dados.fundamental?.escolas[escola]?.total_alunos || 0;
                const total = infAlunos + fundAlunos;

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 500;">${escola}</td>
                    <td>${infAlunos > 0 ? infAlunos : '-'}</td>
                    <td>${fundAlunos > 0 ? fundAlunos : '-'}</td>
                    <td style="font-weight: 600; color: var(--accent-teal);">${total}</td>
                `;
                tbodyEscolas.appendChild(tr);
            });

            // Tabela 2: Professores (Top 50 ordenados por dedicação)
            const tbodyProfessores = document.querySelector('#table-professores tbody');
            tbodyProfessores.innerHTML = '';

            const profsList = Object.entries(dados.professores?.todos || {}).map(([id, info]) => ({
                id,
                ...info
            })).sort((a, b) => b.tempo_total_horas - a.tempo_total_horas);

            profsList.forEach(prof => {
                let segLabel = 'Ambos';
                if (prof.segmento === 'infantil') segLabel = 'Ed. Infantil';
                else if (prof.segmento === 'fundamental') segLabel = 'Ens. Fundamental';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 500;">${prof.nome || 'Avaliador ' + prof.id}</td>
                    <td>${prof.escola || 'N/A'}</td>
                    <td>${segLabel}</td>
                    <td>${prof.total_alunos}</td>
                    <td style="font-weight: 600; color: var(--accent-teal);">${prof.tempo_total_horas.toFixed(1)}h</td>
                    <td>${prof.tempo_medio_aluno.toFixed(0)} min</td>
                `;
                tbodyProfessores.appendChild(tr);
            });

            // Tabela 3: Outliers dos Professores
            const tbodyOutliers = document.querySelector('#table-prof-outliers tbody');
            tbodyOutliers.innerHTML = '';
            let totalOutliersFound = 0;

            profsList.forEach(prof => {
                if (prof.alunos_outliers && prof.alunos_outliers.length > 0) {
                    prof.alunos_outliers.forEach(alunoOut => {
                        totalOutliersFound++;
                        const tr = document.createElement('tr');
                        
                        const media = prof.tempo_medio_aluno;
                        const classif = alunoOut.tempo_minutos < media 
                            ? `<span style="color: var(--accent-teal); font-weight: 600;">✓ Rápido</span>` 
                            : `<span style="color: var(--accent-coral); font-weight: 600;">⚠️ Longo</span>`;

                        tr.innerHTML = `
                            <td style="font-weight: 500;">${prof.nome || 'Avaliador ' + prof.id}</td>
                            <td>${prof.escola || 'N/A'}</td>
                            <td>Aluno ${alunoOut.aluno}</td>
                            <td>${alunoOut.tempo_minutos.toFixed(1)} min</td>
                            <td>${classif}</td>
                        `;
                        tbodyOutliers.appendChild(tr);
                    });
                }
            });

            const cardProfOutliers = document.getElementById('card-prof-outliers');
            if (totalOutliersFound > 0) {
                cardProfOutliers.style.display = 'block';
            } else {
                cardProfOutliers.style.display = 'none';
            }

            // ---- 5. Transição e Exibição do Painel ----
            updateProgressStep(3); // Finalizando

            setTimeout(() => {
                hideProgress();
                
                mainContainer.classList.add('dashboard-active');
                dashboardContainer.classList.add('visible');
                
                dashboardContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                showToast('Painel analítico carregado com sucesso! 📊', 'success');
            }, 600);

        } catch (error) {
            hideProgress();
            showToast(error.message || 'Erro ao carregar dados do dashboard', 'error');
            console.error('Erro no dashboard:', error);
        } finally {
            btnViewDashboard.classList.remove('loading');
            btnViewDashboard.disabled = false;
        }
    });

    // ---- Tab Switcher ----
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetContent = document.getElementById(targetTab);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // ---- Dashboard PDF download convenience button ----
    const btnPdfDashboard = document.getElementById('btn-pdf-dashboard');
    if (btnPdfDashboard) {
        btnPdfDashboard.addEventListener('click', () => {
            form.requestSubmit();
        });
    }
});
