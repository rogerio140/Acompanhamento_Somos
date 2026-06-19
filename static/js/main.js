// ============================================================
// SOMOS EDUCAÇÃO — Flask Report Generator
// Frontend Interactivity
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('report-form');
    const btnGerarRelatorio = document.getElementById('btn-gerar-relatorio');
    const dashboardContainer = document.getElementById('dashboard-container');
    const mainContainer = document.querySelector('.container');
    const municipioRadios = document.querySelectorAll('input[name="municipio"]');
    const segmentosStatus = document.getElementById('segmentos-status');
    const progressOverlay = document.getElementById('progress-overlay');

    // Modal elements
    const modalOverlay = document.getElementById('report-modal-overlay');
    const modalClose = document.getElementById('modal-close');
    const optCompleto = document.getElementById('opt-completo');
    const optPersonalizado = document.getElementById('opt-personalizado');
    const sectionsPanel = document.getElementById('sections-panel');
    const btnGenerateCustom = document.getElementById('btn-generate-custom');

    // ---- Ao selecionar município: verificar segmentos + carregar dashboard ----
    municipioRadios.forEach(radio => {
        radio.addEventListener('change', async (e) => {
            const municipio = e.target.value;
            
            // 1. Verificar segmentos
            await verificarSegmentos(municipio);
            
            // 2. Carregar o dashboard automaticamente
            await carregarDashboard(municipio);
        });
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

            // Habilita o botão de relatório se houver dados
            if (data.infantil || data.fundamental) {
                btnGerarRelatorio.disabled = false;
            } else {
                btnGerarRelatorio.disabled = true;
            }

        } catch (error) {
            console.error('Erro ao verificar segmentos:', error);
            showToast('Erro ao verificar dados do município', 'error');
        }
    }

    // ---- Carregar Dashboard automaticamente ----
    async function carregarDashboard(municipio) {
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

            // Tabela Nova: Ranking de Progresso das Escolas
            const tbodyProgressoEscolas = document.querySelector('#table-progresso-escolas tbody');
            if (tbodyProgressoEscolas) {
                tbodyProgressoEscolas.innerHTML = '';
                
                const escolasProgList = Object.values(dados.escolas_progresso || {}).sort((a, b) => {
                    if (b.progresso !== a.progresso) {
                        return b.progresso - a.progresso; // Decrescente por progresso
                    }
                    if (b.tempo_total_horas !== a.tempo_total_horas) {
                        return b.tempo_total_horas - a.tempo_total_horas; // Decrescente por tempo de dedicação
                    }
                    return a.nome.localeCompare(b.nome); // Crescente por nome
                });

                escolasProgList.forEach((esc, idx) => {
                    const tr = document.createElement('tr');
                    
                    // Escolher cor da barra baseado no progresso
                    let fillStyle = 'var(--gradient-teal)';
                    if (esc.progresso >= 100) {
                        fillStyle = 'var(--gradient-success)';
                    } else if (esc.progresso <= 0) {
                        fillStyle = 'transparent';
                    }

                    tr.innerHTML = `
                        <td style="text-align: center; font-weight: 600; color: var(--text-secondary);">${idx + 1}</td>
                        <td style="font-weight: 600; color: var(--text-primary);">${esc.nome}</td>
                        <td>
                            <div class="progress-bar-container">
                                <div class="progress-bar-fill" style="width: ${esc.progresso}%; background: ${fillStyle};"></div>
                                <span class="progress-bar-text">${esc.progresso.toFixed(1)}%</span>
                            </div>
                        </td>
                        <td style="text-align: center; font-weight: 500;">
                            ${esc.alunos_avaliados} <span style="color: var(--text-muted);">/</span> ${esc.alunos_totais}
                        </td>
                        <td style="text-align: center; font-weight: 600; color: var(--accent-teal);">${esc.tempo_total_horas.toFixed(1)}h</td>
                    `;
                    tbodyProgressoEscolas.appendChild(tr);
                });
            }

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

                // Popular seletor de professores para curva de aprendizagem
                if (window._popularSelectProfessores && dados.professores?.todos) {
                    window._popularSelectProfessores(dados.professores.todos, municipio);
                }
                
                dashboardContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                showToast('Dados carregados com sucesso! 📊', 'success');
            }, 600);

        } catch (error) {
            hideProgress();
            showToast(error.message || 'Erro ao carregar dados', 'error');
            console.error('Erro no dashboard:', error);
        }
    }

    // ---- Modal: Gerar Relatório ----
    btnGerarRelatorio.addEventListener('click', () => {
        // Reset modal state
        sectionsPanel.classList.remove('visible');
        optCompleto.classList.remove('selected');
        optPersonalizado.classList.remove('selected');
        
        // Reset all checkboxes to checked
        document.querySelectorAll('#sections-panel input[type="checkbox"]').forEach(cb => {
            cb.checked = true;
        });
        
        modalOverlay.classList.add('visible');
    });

    // Close modal
    modalClose.addEventListener('click', () => {
        modalOverlay.classList.remove('visible');
    });

    // Close modal clicking overlay background
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
            modalOverlay.classList.remove('visible');
        }
    });

    // Option: Completo → gerar imediatamente com todas as seções
    optCompleto.addEventListener('click', async () => {
        modalOverlay.classList.remove('visible');
        await gerarRelatorio('completo', ['geral', 'estagios', 'horarios', 'professores']);
    });

    // Option: Personalizado → mostrar checkboxes
    optPersonalizado.addEventListener('click', () => {
        optCompleto.classList.remove('selected');
        optPersonalizado.classList.add('selected');
        sectionsPanel.classList.add('visible');
    });

    // Botão de gerar com seções personalizadas
    btnGenerateCustom.addEventListener('click', async () => {
        const checkedSections = Array.from(
            document.querySelectorAll('#sections-panel input[name="secao"]:checked')
        ).map(cb => cb.value);

        if (checkedSections.length === 0) {
            showToast('Selecione ao menos uma seção para o relatório', 'error');
            return;
        }

        modalOverlay.classList.remove('visible');
        await gerarRelatorio('personalizado', checkedSections);
    });

    // ---- Gerar Relatório PDF ----
    async function gerarRelatorio(tipo, secoes) {
        const municipioInput = form.querySelector('input[name="municipio"]:checked');
        if (!municipioInput) {
            showToast('Selecione um município', 'error');
            return;
        }

        const municipio = municipioInput.value;

        // Start loading
        btnGerarRelatorio.classList.add('loading');
        btnGerarRelatorio.disabled = true;
        showProgress();

        try {
            updateProgressStep(0);

            const formData = new FormData();
            formData.append('municipio', municipio);
            formData.append('tipo_relatorio', tipo);
            formData.append('secoes', JSON.stringify(secoes));

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
            btnGerarRelatorio.classList.remove('loading');
            btnGerarRelatorio.disabled = false;
        }
    }

    // ---- Dashboard PDF download convenience button ----
    const btnPdfDashboard = document.getElementById('btn-pdf-dashboard');
    if (btnPdfDashboard) {
        btnPdfDashboard.addEventListener('click', () => {
            btnGerarRelatorio.click();
        });
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

    // ---- Curva de Aprendizagem Individual ----
    const selectProfessor = document.getElementById('select-professor');
    const btnGerarCurva = document.getElementById('btn-gerar-curva');

    // Variável para guardar o municipio atual e dados de professores
    let _municipioAtual = null;
    let _professoresDataAtual = null;

    // Habilitar botão quando professor selecionado
    if (selectProfessor) {
        selectProfessor.addEventListener('change', () => {
            const val = selectProfessor.value;
            if (btnGerarCurva) {
                btnGerarCurva.disabled = !val;
            }
            // Esconder gráficos anteriores ao trocar seleção
            const cardGrafico = document.getElementById('card-curva-grafico');
            const cardRef = document.getElementById('card-curva-referencia');
            if (cardGrafico) cardGrafico.style.display = 'none';
            if (cardRef) cardRef.style.display = 'none';
            document.getElementById('curva-kpis').style.display = 'none';
        });
    }

    if (btnGerarCurva) {
        btnGerarCurva.addEventListener('click', async () => {
            const profId = selectProfessor ? selectProfessor.value : '';
            if (!profId || !_municipioAtual) {
                showToast('Selecione um município e um professor', 'error');
                return;
            }

            // UI de carregamento
            btnGerarCurva.disabled = true;
            btnGerarCurva.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Gerando...';
            const curvaLoading = document.getElementById('curva-loading');
            const cardGrafico = document.getElementById('card-curva-grafico');
            const cardRef = document.getElementById('card-curva-referencia');
            const imgCurva = document.getElementById('img-curva-aprendizagem');

            cardGrafico.style.display = 'block';
            if (curvaLoading) curvaLoading.style.display = 'flex';
            if (imgCurva) imgCurva.style.display = 'none';

            try {
                const response = await fetch('/curva-aprendizagem-professor', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ municipio: _municipioAtual, prof_id: profId })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Erro desconhecido');
                }

                const payload = await response.json();

                // Exibir gráfico
                if (payload.grafico && imgCurva) {
                    imgCurva.src = `data:image/png;base64,${payload.grafico}`;
                    imgCurva.style.display = 'block';
                }
                if (curvaLoading) curvaLoading.style.display = 'none';

                // Atualizar KPIs
                const stats = payload.stats || {};
                const profInfo = _professoresDataAtual ? _professoresDataAtual[profId] : null;
                document.getElementById('curva-kpis').style.display = 'flex';
                document.getElementById('ckpi-media').textContent    = stats.media    != null ? `${stats.media.toFixed(1)} min`    : '-';
                document.getElementById('ckpi-mediana').textContent  = stats.mediana  != null ? `${stats.mediana.toFixed(1)} min`  : '-';
                document.getElementById('ckpi-min').textContent      = stats.min      != null ? `${stats.min.toFixed(1)} min`      : '-';
                document.getElementById('ckpi-max').textContent      = stats.max      != null ? `${stats.max.toFixed(1)} min`      : '-';
                document.getElementById('ckpi-std').textContent      = stats.std      != null ? `±${stats.std.toFixed(1)} min`     : '-';
                document.getElementById('ckpi-total').textContent    = profInfo       ? profInfo.total_alunos                      : '-';

                // Insight automático
                const insightEl = document.getElementById('curva-insight');
                const insightTexto = document.getElementById('curva-insight-texto');
                if (insightEl && insightTexto && stats.media != null && stats.std != null) {
                    const cv = stats.std / stats.media; // Coeficiente de variação
                    let insightMsg = '';
                    if (cv < 0.2) {
                        insightMsg = `✅ Alta consistência: o tempo de avaliação é muito estável (CV = ${(cv*100).toFixed(0)}%). O professor avalia com ritmo regular.`;
                    } else if (cv < 0.4) {
                        insightMsg = `⚡ Variabilidade moderada (CV = ${(cv*100).toFixed(0)}%). Existem algumas variações no tempo de avaliação, o que pode indicar avaliações mais complexas em momentos específicos.`;
                    } else {
                        insightMsg = `⚠️ Alta variabilidade (CV = ${(cv*100).toFixed(0)}%). O tempo de avaliação varia muito — vale investigar se há alunos que demandam mais tempo ou interruções no processo.`;
                    }
                    insightTexto.textContent = insightMsg;
                    insightEl.style.display = 'flex';
                }

                // Popular tabela de referência comparativa
                const curvaRef = payload.curva_referencia;
                const tbodyCurvaRef = document.getElementById('tbody-curva-ref');
                if (curvaRef && tbodyCurvaRef) {
                    tbodyCurvaRef.innerHTML = '';
                    const profDetalhes = profInfo ? (profInfo.alunos_detalhes || []) : [];
                    const profDetalhesSorted = [...profDetalhes].filter(d => d.inicio && d.tempo_minutos > 0)
                        .sort((a, b) => a.inicio.localeCompare(b.inicio));

                    curvaRef.posicoes.forEach((pos, i) => {
                        const medRef = curvaRef.mediana[i];
                        const q25 = curvaRef.q25[i];
                        const q75 = curvaRef.q75[i];

                        // Tempo real do professor nessa posição
                        const tempoProf = profDetalhesSorted[pos - 1] ? profDetalhesSorted[pos - 1].tempo_minutos : null;

                        let comparacaoHtml = '<span style="color: var(--text-muted);">—</span>';
                        if (tempoProf != null) {
                            if (tempoProf < q25) {
                                comparacaoHtml = `<span style="color:#27AE60; font-weight:600;">▼ ${tempoProf.toFixed(1)} min <small>(abaixo Q25)</small></span>`;
                            } else if (tempoProf > q75) {
                                comparacaoHtml = `<span style="color:#E74C3C; font-weight:600;">▲ ${tempoProf.toFixed(1)} min <small>(acima Q75)</small></span>`;
                            } else {
                                comparacaoHtml = `<span style="color:#F39C12; font-weight:600;">◆ ${tempoProf.toFixed(1)} min <small>(dentro da faixa)</small></span>`;
                            }
                        }

                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td style="text-align:center; font-weight:600;">${pos}ª</td>
                            <td style="text-align:center;">${medRef.toFixed(1)}</td>
                            <td style="text-align:center; color: var(--accent-teal);">${q25.toFixed(1)}</td>
                            <td style="text-align:center; color: var(--accent-coral);">${q75.toFixed(1)}</td>
                            <td style="text-align:center;">${comparacaoHtml}</td>
                        `;
                        tbodyCurvaRef.appendChild(tr);
                    });
                    cardRef.style.display = 'block';
                }

                showToast('Curva de aprendizagem gerada! 📈', 'success');

            } catch (err) {
                if (curvaLoading) curvaLoading.style.display = 'none';
                cardGrafico.style.display = 'none';
                showToast(err.message || 'Erro ao gerar curva', 'error');
                console.error('Erro curva de aprendizagem:', err);
            } finally {
                btnGerarCurva.disabled = false;
                btnGerarCurva.innerHTML = '<i class="fa-solid fa-chart-line"></i> Gerar Curva';
            }
        });
    }

    // ---- Função auxiliar para popular select de professores ----
    function popularSelectProfessores(professoresData, municipio) {
        _municipioAtual = municipio;
        _professoresDataAtual = professoresData;

        if (!selectProfessor) return;

        selectProfessor.innerHTML = '<option value="">-- Selecione um professor --</option>';

        const lista = Object.entries(professoresData || {}).map(([id, info]) => ({
            id,
            nome: info.nome || `Avaliador ${id}`,
            escola: info.escola || 'N/A',
            segmento: info.segmento,
            total_alunos: info.total_alunos || 0
        })).sort((a, b) => a.nome.localeCompare(b.nome));

        lista.forEach(prof => {
            const segLabel = prof.segmento === 'infantil' ? 'Ed. Infantil'
                : prof.segmento === 'fundamental' ? 'Ens. Fundamental'
                : 'Ambos';
            const opt = document.createElement('option');
            opt.value = prof.id;
            opt.textContent = `${prof.nome} — ${prof.escola} (${segLabel}, ${prof.total_alunos} alunos)`;
            selectProfessor.appendChild(opt);
        });

        if (btnGerarCurva) btnGerarCurva.disabled = true;
    }

    // Expor função globalmente para ser chamada no carregarDashboard
    window._popularSelectProfessores = popularSelectProfessores;
});
