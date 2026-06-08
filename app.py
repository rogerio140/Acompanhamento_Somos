# -*- coding: utf-8 -*-
"""
Aplicação Flask - Gerador de Relatório de Avaliações
Somos Educação
"""

from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
from io import BytesIO
import traceback
import sys

# Configure stdout to handle emojis in Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


from report_logic import (
    get_db_connection,
    verificar_segmentos_disponiveis,
    coletar_dados,
    criar_pdf,
    calcular_stats,
    detectar_outliers,
    criar_grafico_barras_alunos,
    criar_grafico_barras_tempo,
    criar_grafico_escolas_avaliadas,
    criar_heatmap_escolas_estagios,
    criar_histograma,
    criar_grafico_horarios_alunos,
    criar_heatmap_alunos,
    criar_grafico_outliers,
    criar_grafico_professores,
    criar_grafico_dispersao_professores
)

app = Flask(__name__)


@app.route('/')
def index():
    """Página principal com formulário de geração de relatório"""
    return render_template('index.html')


@app.route('/verificar-segmentos', methods=['POST'])
def verificar_segmentos():
    """Endpoint AJAX para verificar segmentos disponíveis no município"""
    try:
        municipio = request.json.get('municipio')
        if not municipio or municipio not in ('Viradouro', 'Rio Pardo'):
            return jsonify({'error': 'Município inválido'}), 400

        conn = get_db_connection(municipio)
        cursor = conn.cursor()
        segmentos, total_infantil, total_fundamental = verificar_segmentos_disponiveis(cursor)
        cursor.close()
        conn.close()

        return jsonify({
            'infantil': segmentos['infantil'],
            'fundamental': segmentos['fundamental'],
            'total_infantil': total_infantil,
            'total_fundamental': total_fundamental
        })
    except Exception as e:
        print(f"Erro ao verificar segmentos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/obter-dados', methods=['POST'])
def obter_dados():
    """Retorna dados estatísticos e gráficos (base64) em formato JSON"""
    try:
        data = request.json
        municipio = data.get('municipio')
        if not municipio or municipio not in ('Viradouro', 'Rio Pardo'):
            return jsonify({'error': 'Município inválido'}), 400

        print(f"\n📊 [Dashboard] Carregando dados para {municipio}...")

        # 1. Conectar e verificar segmentos
        conn = get_db_connection(municipio)
        cursor = conn.cursor()
        segmentos_disponiveis, _, _ = verificar_segmentos_disponiveis(cursor)
        cursor.close()
        conn.close()

        if not segmentos_disponiveis['infantil'] and not segmentos_disponiveis['fundamental']:
            return jsonify({'error': 'Nenhum segmento com dados disponível para este município.'}), 404

        # 2. Coletar dados
        dados = coletar_dados(municipio, segmentos_disponiveis)

        # 3. Converter buffers dos gráficos para Base64
        import base64
        
        def to_b64(buf):
            if buf is None:
                return None
            try:
                return base64.b64encode(buf.getvalue()).decode('utf-8')
            except Exception as e:
                print(f"Erro ao converter gráfico para base64: {e}")
                return None

        graficos = {}
        
        # Gráficos Gerais
        graficos['alunos_segmento'] = to_b64(criar_grafico_barras_alunos(
            dados['infantil'], dados['fundamental']
        ))
        graficos['tempo_medio'] = to_b64(criar_grafico_barras_tempo(
            dados['infantil'], dados['fundamental']
        ))
        
        escolas_inf = dados['infantil']['escolas'] if dados['infantil'] else {}
        escolas_fund = dados['fundamental']['escolas'] if dados['fundamental'] else {}
        graficos['escolas_avaliadas'] = to_b64(criar_grafico_escolas_avaliadas(
            escolas_inf, escolas_fund
        ))
        
        tempos_inf = dados['infantil']['tempos'] if dados['infantil'] else []
        tempos_fund = dados['fundamental']['tempos'] if dados['fundamental'] else []
        graficos['histograma_tempos'] = to_b64(criar_histograma(tempos_inf, tempos_fund))
        
        # Heatmaps de Estágios
        if dados['infantil'] and dados['infantil']['escolas']:
            graficos['heatmap_estagios_infantil'] = to_b64(criar_heatmap_escolas_estagios(
                dados['infantil']['escolas'], "Distribuição de Estágios por Escola - Educação Infantil"
            ))
        if dados['fundamental'] and dados['fundamental']['escolas']:
            graficos['heatmap_estagios_fundamental'] = to_b64(criar_heatmap_escolas_estagios(
                dados['fundamental']['escolas'], "Distribuição de Estágios por Escola - Ensino Fundamental"
            ))
            
        # Horários
        if dados['horarios']:
            graficos['horarios_alunos'] = to_b64(criar_grafico_horarios_alunos(
                dados['horarios']['horas'], dados['horarios']['total_alunos']
            ))
            graficos['heatmap_horarios'] = to_b64(criar_heatmap_alunos(
                dados['horarios']['hora_dia']
            ))
            
        # Professores
        if dados['professores']['todos']:
            graficos['professores_dedicacao'] = to_b64(criar_grafico_professores(
                dados['professores']['todos']
            ))
            graficos['professores_dispersao'] = to_b64(criar_grafico_dispersao_professores(
                dados['professores']['todos']
            ))
            
        # Outliers
        if dados['infantil'] and dados['infantil']['tempos']:
            outliers_inf = detectar_outliers(dados['infantil']['tempos'])
            graficos['outliers_infantil'] = to_b64(criar_grafico_outliers(
                dados['infantil']['tempos'], outliers_inf, "Análise de Outliers - Educação Infantil"
            ))
        if dados['fundamental'] and dados['fundamental']['tempos']:
            outliers_fund = detectar_outliers(dados['fundamental']['tempos'])
            graficos['outliers_fundamental'] = to_b64(criar_grafico_outliers(
                dados['fundamental']['tempos'], outliers_fund, "Análise de Outliers - Ensino Fundamental"
            ))

        # 4. Formatar e estruturar os dados para JSON
        resposta_dados = {}
        
        # Horários
        if dados.get('horarios'):
            h = dados['horarios']
            resposta_dados['horarios'] = {
                'total_alunos': h['total_alunos'],
                'horas': {str(k): v for k, v in h['horas'].items()},
                'dias': {str(k): v for k, v in h['dias'].items()}
            }
            
        # Processar segmentos
        def serializar_segmento(seg_data):
            if not seg_data:
                return None
            stats = calcular_stats(seg_data['tempos'])
            outliers = detectar_outliers(seg_data['tempos'])
            
            # Converter defaultdict para dict comum e garantir que as chaves sejam strings
            escolas_limpas = {}
            for esc_nome, esc_info in seg_data['escolas'].items():
                escolas_limpas[str(esc_nome)] = {str(k): v for k, v in esc_info.items()}
                
            return {
                'total_alunos': len(seg_data['tempos']),
                'stats': stats,
                'outliers_count': len(outliers['outliers']),
                'limite_inferior': outliers['limite_inferior'],
                'limite_superior': outliers['limite_superior'],
                'escolas': escolas_limpas
            }
            
        resposta_dados['infantil'] = serializar_segmento(dados.get('infantil'))
        resposta_dados['fundamental'] = serializar_segmento(dados.get('fundamental'))
        
        # Professores
        profs_todos = {}
        if dados.get('professores') and dados['professores'].get('todos'):
            for prof_id, prof_info in dados['professores']['todos'].items():
                profs_todos[str(prof_id)] = {
                    'nome': prof_info.get('nome'),
                    'escola': prof_info.get('escola'),
                    'segmento': prof_info.get('segmento'),
                    'total_alunos': prof_info.get('total_alunos'),
                    'tempo_total_horas': round(prof_info.get('tempo_total_horas', 0), 2),
                    'tempo_medio_aluno': round(prof_info.get('tempo_medio_aluno', 0), 2),
                    'alunos_outliers': prof_info.get('alunos_outliers', [])
                }
                
        resposta_dados['professores'] = {
            'todos': profs_todos,
            'total_professores': len(profs_todos)
        }

        return jsonify({
            'dados': resposta_dados,
            'graficos': graficos
        })

    except Exception as e:
        print(f"Erro ao obter dados: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/gerar-relatorio', methods=['POST'])
def gerar_relatorio():
    """Gera o relatório PDF e retorna para download"""
    try:
        municipio = request.form.get('municipio')
        tipo_relatorio = request.form.get('tipo_relatorio', 'completo')

        if not municipio or municipio not in ('Viradouro', 'Rio Pardo'):
            return jsonify({'error': 'Município inválido'}), 400

        if tipo_relatorio not in ('reduzido', 'completo'):
            return jsonify({'error': 'Tipo de relatório inválido'}), 400

        print(f"\n{'='*60}")
        print(f"Gerando relatório: {municipio} - {tipo_relatorio}")
        print(f"{'='*60}")

        # 1. Conectar e verificar segmentos
        conn = get_db_connection(municipio)
        cursor = conn.cursor()
        segmentos_disponiveis, _, _ = verificar_segmentos_disponiveis(cursor)
        cursor.close()
        conn.close()

        if not segmentos_disponiveis['infantil'] and not segmentos_disponiveis['fundamental']:
            return jsonify({'error': 'Nenhum segmento com dados disponível para gerar relatório.'}), 404

        # 2. Coletar dados
        print(f"\n📊 Coletando dados de {municipio}...")
        dados = coletar_dados(municipio, segmentos_disponiveis)

        # 3. Gerar PDF
        print(f"\n📄 Gerando relatório {tipo_relatorio}...")
        pdf_buffer = criar_pdf(dados, municipio, segmentos_disponiveis, tipo_relatorio)

        # 4. Preparar nome do arquivo
        nome_arquivo = f"relatorio_avaliacoes_{municipio.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        print(f"\n✅ Relatório gerado com sucesso: {nome_arquivo}")
        print(f"📊 Tamanho: {pdf_buffer.getbuffer().nbytes / 1024:.1f} KB")

        # 5. Enviar PDF para download
        pdf_output = BytesIO(pdf_buffer.getvalue())
        return send_file(
            pdf_output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nome_arquivo
        )

    except Exception as e:
        print(f"\n❌ Erro ao gerar relatório: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Erro ao gerar relatório: {str(e)}'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 SOMOS EDUCAÇÃO — Gerador de Relatórios")
    print("=" * 60)
    print("Acesse: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
