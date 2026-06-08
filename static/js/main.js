// ============================================================
// SOMOS EDUCAÇÃO — Flask Report Generator
// Frontend Interactivity
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('report-form');
    const btnSubmit = document.getElementById('btn-submit');
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

            // Habilita o botão se houver dados
            if (data.infantil || data.fundamental) {
                btnSubmit.disabled = false;
            } else {
                btnSubmit.disabled = true;
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
});
