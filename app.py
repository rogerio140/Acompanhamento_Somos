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
    criar_pdf
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
