# -*- coding: utf-8 -*-
"""
Módulo de lógica de relatórios — extraído de acompanhamento_uso_sistema7.py

Contém todas as funções de:
- Conexão com banco de dados PostgreSQL
- Coleta de dados (infantil / fundamental)
- Geração de gráficos Matplotlib
- Geração de PDF com ReportLab
"""

import psycopg2
from datetime import datetime
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import re

# Registrar fonte Unicode
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    FONT_NAME = 'DejaVuSans'
except:
    FONT_NAME = 'Helvetica'


# ============================================================================
# FUNÇÕES DE DADOS
# ============================================================================

def get_db_connection(municipio=None):
    """Retorna conexão com o banco de dados do município selecionado"""
    configs = {
        'Viradouro': {
            "host": "dpg-d7jn378sfn5c738s2veg-a.virginia-postgres.render.com",
            "port": "5432",
            "dbname": "somos_educa_26_vd",
            "user": "somos_educa_26_rp_user",
            "password": "mPaPHRDIeuGiHxV3sNKnXH3N1BlmF4Ry",
            "sslmode": "require"
        },
        'Rio Pardo': {
            "host": "dpg-d7jn378sfn5c738s2veg-a.virginia-postgres.render.com",
            "port": "5432",
            "dbname": "somos_educa_26_rp",
            "user": "somos_educa_26_rp_user",
            "password": "mPaPHRDIeuGiHxV3sNKnXH3N1BlmF4Ry",
            "sslmode": "require"
        }
    }

    if municipio and municipio in configs:
        return psycopg2.connect(**configs[municipio])
    else:
        raise ValueError(f"Município não reconhecido: {municipio}")


def verificar_segmentos_disponiveis(cursor):
    """Verifica quais segmentos (infantil/fundamental) têm dados no banco"""
    segmentos = {}

    # Verificar Educação Infantil
    cursor.execute("""
        SELECT COUNT(*) FROM avaliacoes_direitos 
        WHERE inicio_avaliacao IS NOT NULL AND fim_avaliacao IS NOT NULL
    """)
    total_infantil = cursor.fetchone()[0]
    segmentos['infantil'] = total_infantil > 0

    # Verificar Ensino Fundamental
    cursor.execute("""
        SELECT COUNT(*) FROM avaliacoes_habilidades 
        WHERE inicio_avaliacao IS NOT NULL AND fim_avaliacao IS NOT NULL
    """)
    total_fundamental = cursor.fetchone()[0]
    segmentos['fundamental'] = total_fundamental > 0

    print(f"\n📊 Segmentos disponíveis:")
    print(f"   Educação Infantil: {'✅' if segmentos['infantil'] else '❌'} ({total_infantil} registros)")
    print(f"   Ensino Fundamental: {'✅' if segmentos['fundamental'] else '❌'} ({total_fundamental} registros)")

    return segmentos, total_infantil, total_fundamental


def calcular_stats(tempos):
    """Calcula estatísticas básicas de uma lista de tempos"""
    if not tempos:
        return None
    return {
        'media': np.mean(tempos),
        'mediana': np.median(tempos),
        'std': np.std(tempos),
        'min': np.min(tempos),
        'max': np.max(tempos),
        'total_alunos': len(tempos),
        'q1': np.percentile(tempos, 25),
        'q3': np.percentile(tempos, 75)
    }


def detectar_outliers(tempos, metodo='iqr'):
    """Detecta outliers em uma lista de tempos"""
    if len(tempos) < 4:
        return {'outliers': [], 'limite_inferior': None, 'limite_superior': None, 'q1': None, 'q3': None, 'media': None, 'mediana': None}

    tempos_array = np.array(tempos)

    q1 = np.percentile(tempos_array, 25)
    q3 = np.percentile(tempos_array, 75)
    iqr = q3 - q1
    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    outliers = [t for t in tempos if t < limite_inferior or t > limite_superior]

    return {
        'outliers': sorted(outliers),
        'limite_inferior': limite_inferior,
        'limite_superior': limite_superior,
        'q1': q1,
        'q3': q3,
        'media': np.mean(tempos_array),
        'mediana': np.median(tempos_array)
    }


def calcular_tempo_dedicacao_professor(cursor, coluna_prof, tabela):
    """Calcula o tempo de dedicação de cada professor"""
    professores = defaultdict(lambda: {
        'tempo_total_minutos': 0, 
        'total_alunos': 0, 
        'alunos_tempos': [],
        'alunos_detalhes': [],
        'escola': ''
    })

    if not coluna_prof:
        return professores

    nomes_professores = {}
    try:
        cursor.execute("SELECT id_plurall, nome FROM professores")
        for prof_id, nome in cursor.fetchall():
            nomes_professores[prof_id] = nome
    except:
        pass

    query = f"""
        SELECT 
            av.{coluna_prof} as prof_id,
            av.aluno_matricula,
            MIN(av.inicio_avaliacao) as primeira_questao,
            MAX(av.fim_avaliacao) as ultima_questao,
            e.nome as escola_nome
        FROM {tabela} av
        JOIN alunos a ON av.aluno_matricula = a.matricula
        JOIN turmas t ON a.turma_id = t.id
        JOIN escolas e ON t.escola_id = e.id
        WHERE av.inicio_avaliacao IS NOT NULL 
          AND av.fim_avaliacao IS NOT NULL
          AND av.{coluna_prof} IS NOT NULL
        GROUP BY av.{coluna_prof}, av.aluno_matricula, e.nome
        ORDER BY av.{coluna_prof}, av.aluno_matricula
    """

    cursor.execute(query)

    for prof_id, aluno, inicio, fim, escola in cursor.fetchall():
        tempo_minutos = (fim - inicio).total_seconds() / 60

        prof_id_str = str(prof_id)
        professores[prof_id_str]['tempo_total_minutos'] += tempo_minutos
        professores[prof_id_str]['total_alunos'] += 1
        professores[prof_id_str]['alunos_tempos'].append(tempo_minutos)
        professores[prof_id_str]['alunos_detalhes'].append({
            'aluno': aluno,
            'tempo_minutos': tempo_minutos,
            'inicio': inicio.strftime('%d/%m/%Y %H:%M:%S'),
            'fim': fim.strftime('%d/%m/%Y %H:%M:%S')
        })
        professores[prof_id_str]['escola'] = escola
        professores[prof_id_str]['nome'] = nomes_professores.get(prof_id, f"Avaliador {prof_id}")

    for prof_id in professores:
        tempos = professores[prof_id]['alunos_tempos']
        if tempos:
            professores[prof_id]['tempo_medio_aluno'] = np.mean(tempos)
            professores[prof_id]['tempo_mediano_aluno'] = np.median(tempos)
            professores[prof_id]['tempo_min_aluno'] = np.min(tempos)
            professores[prof_id]['tempo_max_aluno'] = np.max(tempos)
            professores[prof_id]['tempo_std_aluno'] = np.std(tempos) if len(tempos) > 1 else 0
            professores[prof_id]['tempo_total_horas'] = professores[prof_id]['tempo_total_minutos'] / 60

            outliers_prof = detectar_outliers(tempos)
            professores[prof_id]['outliers'] = outliers_prof['outliers']
            professores[prof_id]['alunos_outliers'] = [
                det for det in professores[prof_id]['alunos_detalhes']
                if det['tempo_minutos'] in outliers_prof['outliers']
            ]

    return professores


def verificar_estrutura_tabelas(cursor):
    """Verifica a estrutura das tabelas para identificar a coluna correta do professor"""
    print("Verificando estrutura das tabelas...")

    coluna_prof_direitos = None
    coluna_prof_habilidades = None

    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'avaliacoes_direitos'
            ORDER BY ordinal_position
        """)
        colunas_direitos = [col[0] for col in cursor.fetchall()]

        for col in colunas_direitos:
            if 'avaliador' in col.lower() or 'prof' in col.lower() or 'user' in col.lower():
                coluna_prof_direitos = col
                break
    except:
        pass

    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'avaliacoes_habilidades'
            ORDER BY ordinal_position
        """)
        colunas_habilidades = [col[0] for col in cursor.fetchall()]

        for col in colunas_habilidades:
            if 'avaliador' in col.lower() or 'prof' in col.lower() or 'user' in col.lower():
                coluna_prof_habilidades = col
                break
    except:
        pass

    print(f"Coluna de professor em avaliacoes_direitos: {coluna_prof_direitos}")
    print(f"Coluna de professor em avaliacoes_habilidades: {coluna_prof_habilidades}")

    return coluna_prof_direitos, coluna_prof_habilidades


def coletar_dados_segmento(cursor, segmento, coluna_prof):
    """Coleta dados de um segmento específico (infantil ou fundamental)"""

    if segmento == 'infantil':
        tabela = 'avaliacoes_direitos'
    else:
        tabela = 'avaliacoes_habilidades'

    dados = {
        'tempos': [],
        'escolas': defaultdict(lambda: defaultdict(int)),
        'alunos_horarios': [],
        'professores': {}
    }

    # Coletar tempos e escolas
    cursor.execute(f"""
        SELECT 
            av.aluno_matricula,
            MIN(av.inicio_avaliacao) as primeira,
            MAX(av.fim_avaliacao) as ultima,
            e.nome as escola_nome
        FROM {tabela} av
        JOIN alunos a ON av.aluno_matricula = a.matricula
        JOIN turmas t ON a.turma_id = t.id
        JOIN escolas e ON t.escola_id = e.id
        WHERE av.inicio_avaliacao IS NOT NULL AND av.fim_avaliacao IS NOT NULL
        GROUP BY av.aluno_matricula, e.nome
    """)

    for aluno, primeira, ultima, escola in cursor.fetchall():
        tempo = (ultima - primeira).total_seconds() / 60
        dados['tempos'].append(tempo)
        dados['alunos_horarios'].append({
            'aluno': aluno,
            'hora_finalizacao': ultima.hour,
            'dia_finalizacao': ultima.strftime('%A')
        })
        dados['escolas'][escola]['total_alunos'] += 1

    # Coletar estágios por escola
    cursor.execute(f"""
        SELECT 
            e.nome as escola_nome,
            av.estagio_numero,
            COUNT(*) as total
        FROM {tabela} av
        JOIN alunos a ON av.aluno_matricula = a.matricula
        JOIN turmas t ON a.turma_id = t.id
        JOIN escolas e ON t.escola_id = e.id
        WHERE av.estagio_numero IS NOT NULL
        GROUP BY e.nome, av.estagio_numero
    """)

    for escola, estagio, total in cursor.fetchall():
        dados['escolas'][escola][estagio] = total

    # Coletar dados de professores
    if coluna_prof:
        dados['professores'] = calcular_tempo_dedicacao_professor(cursor, coluna_prof, tabela)

    return dados


def coletar_dados(municipio, segmentos_disponiveis):
    """Coleta dados apenas dos segmentos disponíveis"""
    conn = get_db_connection(municipio)
    cursor = conn.cursor()

    print("Coletando dados...")

    # Verificar estrutura das tabelas
    coluna_prof_direitos, coluna_prof_habilidades = verificar_estrutura_tabelas(cursor)

    dados = {
        'infantil': None,
        'fundamental': None,
        'horarios': None,
        'professores': {'infantil': {}, 'fundamental': {}, 'todos': {}}
    }

    # Coletar dados apenas dos segmentos disponíveis
    if segmentos_disponiveis['infantil']:
        print("\n📚 Coletando dados da Educação Infantil...")
        dados['infantil'] = coletar_dados_segmento(cursor, 'infantil', coluna_prof_direitos)
        print(f"   ✅ {len(dados['infantil']['tempos'])} alunos avaliados")
        print(f"   ✅ {len(dados['infantil']['escolas'])} escolas")
        print(f"   ✅ {len(dados['infantil']['professores'])} professores")

    if segmentos_disponiveis['fundamental']:
        print("\n📚 Coletando dados do Ensino Fundamental...")
        dados['fundamental'] = coletar_dados_segmento(cursor, 'fundamental', coluna_prof_habilidades)
        print(f"   ✅ {len(dados['fundamental']['tempos'])} alunos avaliados")
        print(f"   ✅ {len(dados['fundamental']['escolas'])} escolas")
        print(f"   ✅ {len(dados['fundamental']['professores'])} professores")

    # Processar horários
    todos_horarios = []
    if dados['infantil']:
        todos_horarios.extend(dados['infantil']['alunos_horarios'])
    if dados['fundamental']:
        todos_horarios.extend(dados['fundamental']['alunos_horarios'])

    dias_map = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }

    contagem_horas = defaultdict(int)
    contagem_dias = defaultdict(int)
    contagem_hora_dia = defaultdict(lambda: defaultdict(int))

    for aluno_info in todos_horarios:
        hora = aluno_info['hora_finalizacao']
        dia_ing = aluno_info['dia_finalizacao']
        dia_pt = dias_map.get(dia_ing, dia_ing)

        contagem_horas[hora] += 1
        contagem_dias[dia_pt] += 1
        contagem_hora_dia[hora][dia_pt] += 1

    dados['horarios'] = {
        'horas': contagem_horas,
        'dias': contagem_dias,
        'hora_dia': contagem_hora_dia,
        'total_alunos': len(todos_horarios)
    }

    # Combinar professores
    todos_professores = {}
    if dados['infantil']:
        for prof_id, prof_data in dados['infantil']['professores'].items():
            todos_professores[prof_id] = prof_data.copy()
            todos_professores[prof_id]['segmento'] = 'infantil'

    if dados['fundamental']:
        for prof_id, prof_data in dados['fundamental']['professores'].items():
            if prof_id in todos_professores:
                todos_professores[prof_id]['tempo_total_minutos'] += prof_data['tempo_total_minutos']
                todos_professores[prof_id]['total_alunos'] += prof_data['total_alunos']
                todos_professores[prof_id]['alunos_tempos'].extend(prof_data['alunos_tempos'])
                todos_professores[prof_id]['alunos_detalhes'].extend(prof_data['alunos_detalhes'])
                todos_professores[prof_id]['tempo_total_horas'] = todos_professores[prof_id]['tempo_total_minutos'] / 60
                todos_professores[prof_id]['segmento'] = 'ambos'
            else:
                todos_professores[prof_id] = prof_data.copy()
                todos_professores[prof_id]['segmento'] = 'fundamental'

    # Recalcular estatísticas para professores combinados
    for prof_id in todos_professores:
        tempos = todos_professores[prof_id]['alunos_tempos']
        if tempos:
            todos_professores[prof_id]['tempo_medio_aluno'] = np.mean(tempos)
            todos_professores[prof_id]['tempo_mediano_aluno'] = np.median(tempos)
            todos_professores[prof_id]['tempo_min_aluno'] = np.min(tempos)
            todos_professores[prof_id]['tempo_max_aluno'] = np.max(tempos)
            todos_professores[prof_id]['tempo_std_aluno'] = np.std(tempos) if len(tempos) > 1 else 0

    dados['professores']['todos'] = todos_professores

    cursor.close()
    conn.close()

    return dados


# ============================================================================
# FUNÇÕES DE GRÁFICOS
# ============================================================================

def criar_grafico_barras_alunos(dados_infantil, dados_fundamental):
    """Cria gráfico de barras comparativo de número de alunos avaliados"""
    fig, ax = plt.subplots(figsize=(8, 5))

    segmentos = []
    alunos = []

    if dados_infantil:
        segmentos.append('Educação Infantil')
        alunos.append(len(dados_infantil['tempos']))

    if dados_fundamental:
        segmentos.append('Ensino Fundamental')
        alunos.append(len(dados_fundamental['tempos']))

    if not segmentos:
        return None

    cores = ['#FF6B6B', '#4ECDC4']
    barras = ax.bar(segmentos, alunos, color=cores[:len(segmentos)], alpha=0.8, edgecolor='black', linewidth=1.5)

    for bar, total in zip(barras, alunos):
        if total > 0:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                   f'{int(total)}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_ylabel('Número de Alunos Avaliados', fontsize=11, fontweight='bold')
    ax.set_title('Total de Alunos Avaliados por Segmento', fontsize=13, fontweight='bold', pad=15)
    ax.set_ylim(0, max(alunos) * 1.2 if max(alunos) > 0 else 10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_barras_tempo(dados_infantil, dados_fundamental):
    """Cria gráfico de barras comparativo de tempos médios"""
    fig, ax = plt.subplots(figsize=(8, 5))

    segmentos = []
    tempos_horas = []
    erros = []

    if dados_infantil and dados_infantil['tempos']:
        segmentos.append('Educação Infantil')
        tempos_horas.append(np.mean(dados_infantil['tempos']) / 60)
        erros.append(np.std(dados_infantil['tempos']) / 60 if len(dados_infantil['tempos']) > 1 else 0)

    if dados_fundamental and dados_fundamental['tempos']:
        segmentos.append('Ensino Fundamental')
        tempos_horas.append(np.mean(dados_fundamental['tempos']) / 60)
        erros.append(np.std(dados_fundamental['tempos']) / 60 if len(dados_fundamental['tempos']) > 1 else 0)

    if not segmentos:
        return None

    cores = ['#FF6B6B', '#4ECDC4']
    barras = ax.bar(segmentos, tempos_horas, yerr=erros, capsize=8, 
                    color=cores[:len(segmentos)], alpha=0.8, edgecolor='black', linewidth=1.5)

    for bar, tempo in zip(barras, tempos_horas):
        if tempo > 0:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
                   f'{tempo:.1f}h', ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_ylabel('Tempo Médio (horas)', fontsize=11, fontweight='bold')
    ax.set_title('Tempo Médio de Avaliação por Aluno', fontsize=13, fontweight='bold', pad=15)
    ax.set_ylim(0, max(tempos_horas) * 1.3 if max(tempos_horas) > 0 else 1)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_escolas_avaliadas(escolas_infantil, escolas_fundamental):
    """Cria gráfico de barras das escolas que realizaram avaliações"""
    todas_escolas = list(set(escolas_infantil.keys()) | set(escolas_fundamental.keys()))
    todas_escolas.sort()

    if not todas_escolas:
        return None

    fig, ax = plt.subplots(figsize=(10, max(6, len(todas_escolas) * 0.5)))

    alunos_infantil = [escolas_infantil.get(escola, {}).get('total_alunos', 0) for escola in todas_escolas]
    alunos_fundamental = [escolas_fundamental.get(escola, {}).get('total_alunos', 0) for escola in todas_escolas]

    x = np.arange(len(todas_escolas))
    width = 0.35

    barras1 = ax.bar(x - width/2, alunos_infantil, width, label='Educação Infantil', 
                     color='#FF6B6B', alpha=0.8, edgecolor='black')
    barras2 = ax.bar(x + width/2, alunos_fundamental, width, label='Ensino Fundamental', 
                     color='#4ECDC4', alpha=0.8, edgecolor='black')

    for bar in barras1:
        if bar.get_height() > 0:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                   f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=8)

    for bar in barras2:
        if bar.get_height() > 0:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                   f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('Escolas', fontsize=11, fontweight='bold')
    ax.set_ylabel('Número de Alunos Avaliados', fontsize=11, fontweight='bold')
    ax.set_title('Alunos Avaliados por Escola e Segmento', fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(todas_escolas, rotation=45, ha='right', fontsize=9)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_heatmap_escolas_estagios(escolas_dados, titulo):
    """Cria mapa de calor das escolas e estágios de desenvolvimento"""
    if not escolas_dados:
        return None

    escolas = list(escolas_dados.keys())
    estagios = list(range(1, 6))

    dados = np.zeros((len(escolas), len(estagios)))
    for i, escola in enumerate(escolas):
        for j, estagio in enumerate(estagios):
            dados[i, j] = escolas_dados[escola].get(estagio, 0)

    fig, ax = plt.subplots(figsize=(12, max(6, len(escolas) * 0.5)))

    im = ax.imshow(dados, cmap='YlOrRd', aspect='auto')

    ax.set_xticks(range(len(estagios)))
    ax.set_xticklabels([f'Estágio {e}' for e in estagios], fontsize=10, fontweight='bold')
    ax.set_yticks(range(len(escolas)))
    ax.set_yticklabels(escolas, fontsize=8)

    ax.set_xlabel('Estágios de Desenvolvimento', fontsize=11, fontweight='bold')
    ax.set_ylabel('Escolas', fontsize=11, fontweight='bold')
    ax.set_title(titulo, fontsize=12, fontweight='bold', pad=15)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Número de Alunos', fontsize=10)

    for i in range(len(escolas)):
        for j in range(len(estagios)):
            valor = dados[i, j]
            if valor > 0:
                text_color = 'white' if valor > np.max(dados)/2 else 'black'
                ax.text(j, i, str(int(valor)), ha='center', va='center', 
                       color=text_color, fontsize=8, fontweight='bold')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_histograma(tempos_infantil, tempos_fundamental):
    """Cria histogramas lado a lado da distribuição dos tempos"""
    tempos_lista = []
    titulos = []
    cores = []

    if tempos_infantil:
        tempos_lista.append(tempos_infantil)
        titulos.append('Educação Infantil')
        cores.append('#FF6B6B')

    if tempos_fundamental:
        tempos_lista.append(tempos_fundamental)
        titulos.append('Ensino Fundamental')
        cores.append('#4ECDC4')

    if not tempos_lista:
        return None

    fig, axes = plt.subplots(1, len(tempos_lista), figsize=(6*len(tempos_lista), 4))
    if len(tempos_lista) == 1:
        axes = [axes]

    for ax, tempos, titulo, cor in zip(axes, tempos_lista, titulos, cores):
        ax.hist(tempos, bins=min(10, len(tempos)), color=cor, alpha=0.7, edgecolor='black')
        ax.axvline(np.mean(tempos), color='red', linestyle='--', 
                   linewidth=1.5, label=f'Média: {np.mean(tempos):.1f}min')
        ax.set_xlabel('Tempo (minutos)', fontsize=9)
        ax.set_ylabel('Número de Alunos', fontsize=9)
        ax.set_title(titulo, fontsize=10, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.suptitle('Distribuição dos Tempos de Avaliação por Aluno', fontsize=12, fontweight='bold', y=1.05)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_horarios_alunos(contagem_horas, total_alunos):
    """Cria gráfico de barras dos horários de finalização das avaliações"""
    fig, ax = plt.subplots(figsize=(10, 5))

    horas = list(range(24))
    valores = [contagem_horas.get(h, 0) for h in horas]

    cores = ['#4ECDC4' if 8 <= h <= 17 else '#FF6B6B' for h in horas]
    barras = ax.bar(horas, valores, color=cores, alpha=0.8, edgecolor='black', linewidth=0.5)

    if contagem_horas:
        hora_pico = max(contagem_horas, key=contagem_horas.get)
        barras[hora_pico].set_color('#FFD93D')
        barras[hora_pico].set_edgecolor('red')
        barras[hora_pico].set_linewidth(2)

    ax.set_xlabel('Horário do Dia', fontsize=11, fontweight='bold')
    ax.set_ylabel('Número de Alunos Avaliados', fontsize=11, fontweight='bold')
    ax.set_title(f'Alunos Avaliados por Horário de Finalização\nTotal de alunos avaliados: {total_alunos}', 
                fontsize=12, fontweight='bold', pad=15)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f'{h}:00' for h in range(0, 24, 2)], rotation=45)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_heatmap_alunos(contagem_hora_dia):
    """Cria mapa de calor de alunos avaliados por hora e dia"""
    fig, ax = plt.subplots(figsize=(10, 6))

    dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    horas = list(range(6, 22))

    dados = np.zeros((len(horas), len(dias)))
    for i, hora in enumerate(horas):
        for j, dia in enumerate(dias):
            dados[i, j] = contagem_hora_dia[hora].get(dia, 0)

    im = ax.imshow(dados, cmap='YlOrRd', aspect='auto')

    ax.set_xticks(range(len(dias)))
    ax.set_xticklabels(dias, rotation=45, ha='right', fontsize=9)
    ax.set_yticks(range(len(horas)))
    ax.set_yticklabels([f'{h}:00' for h in horas], fontsize=9)

    ax.set_xlabel('Dia da Semana', fontsize=11, fontweight='bold')
    ax.set_ylabel('Horário do Dia', fontsize=11, fontweight='bold')
    ax.set_title('Alunos Avaliados por Horário e Dia da Semana', fontsize=12, fontweight='bold', pad=15)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Número de Alunos Avaliados', fontsize=10)

    for i in range(len(horas)):
        for j in range(len(dias)):
            valor = dados[i, j]
            if valor > 0:
                text_color = 'white' if valor > np.max(dados)/2 else 'black'
                ax.text(j, i, str(int(valor)), ha='center', va='center', 
                       color=text_color, fontsize=7, fontweight='bold')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_outliers(tempos, limites, titulo):
    """Cria gráfico de boxplot para visualização de outliers"""
    if not tempos:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))

    bp = ax.boxplot(tempos, vert=False, patch_artist=True)
    bp['boxes'][0].set_facecolor('#4ECDC4')
    bp['boxes'][0].set_alpha(0.7)

    y = np.ones(len(tempos)) * 1
    ax.scatter(tempos, y, alpha=0.5, color='#2C3E50', s=30, zorder=3)

    if limites['outliers']:
        outliers_y = np.ones(len(limites['outliers']))
        ax.scatter(limites['outliers'], outliers_y, alpha=0.8, color='red', s=50, 
                  zorder=4, edgecolors='darkred', linewidth=1.5, label='Outliers')

    if limites['limite_inferior'] is not None:
        ax.axvline(limites['limite_inferior'], color='orange', linestyle='--', 
                  linewidth=1.5, alpha=0.7, label=f'Limite Inferior: {limites["limite_inferior"]:.1f}min')
    if limites['limite_superior'] is not None:
        ax.axvline(limites['limite_superior'], color='orange', linestyle='--', 
                  linewidth=1.5, alpha=0.7, label=f'Limite Superior: {limites["limite_superior"]:.1f}min')

    if limites['media'] is not None:
        ax.axvline(limites['media'], color='blue', linestyle='-', linewidth=1.5, 
                  alpha=0.7, label=f'Média: {limites["media"]:.1f}min')
    if limites['mediana'] is not None:
        ax.axvline(limites['mediana'], color='green', linestyle='-', linewidth=1.5, 
                  alpha=0.7, label=f'Mediana: {limites["mediana"]:.1f}min')

    ax.set_xlabel('Tempo (minutos)', fontsize=11, fontweight='bold')
    ax.set_title(titulo, fontsize=13, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_professores(professores_dados):
    """Cria gráfico de barras dos professores com mais tempo de dedicação"""
    if not professores_dados:
        return None

    professores_ordenados = sorted(professores_dados.items(), key=lambda x: x[1].get('tempo_total_horas', 0), reverse=True)[:15]

    if not professores_ordenados:
        return None

    fig, ax = plt.subplots(figsize=(12, 6))

    nomes = [p[1].get('nome', f'Professor {p[0][:8]}') for p in professores_ordenados]
    tempos = [p[1].get('tempo_total_horas', 0) for p in professores_ordenados]
    alunos = [p[1].get('total_alunos', 0) for p in professores_ordenados]

    max_tempo = max(tempos) if tempos else 1
    cores = plt.cm.RdYlGn([t/max_tempo for t in tempos])
    barras = ax.barh(range(len(nomes)), tempos, color=cores, alpha=0.8, edgecolor='black')

    for i, (tempo, n_alunos) in enumerate(zip(tempos, alunos)):
        if tempo > 0:
            ax.text(tempo + 0.1, i, f'{tempo:.1f}h ({n_alunos} alunos)', 
                   va='center', fontsize=8, fontweight='bold')

    ax.set_yticks(range(len(nomes)))
    ax.set_yticklabels(nomes, fontsize=8)
    ax.set_xlabel('Tempo Total (horas)', fontsize=11, fontweight='bold')
    ax.set_title('Top 15 Professores - Tempo Total de Dedicação em Avaliações', 
                fontsize=13, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')
    ax.invert_yaxis()

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


def criar_grafico_dispersao_professores(professores_dados):
    """Cria gráfico de dispersão: tempo total vs número de alunos por professor"""
    if not professores_dados:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    tempos = [p.get('tempo_total_horas', 0) for p in professores_dados.values()]
    alunos = [p.get('total_alunos', 0) for p in professores_dados.values()]
    nomes = [p.get('nome', f'Professor {p_id[:8]}') for p_id, p in professores_dados.items()]

    if len(tempos) > 2:
        tempo_media = np.mean(tempos)
        tempo_std = np.std(tempos)
        alunos_media = np.mean(alunos)
        alunos_std = np.std(alunos)
    else:
        tempo_media = 0
        tempo_std = 1
        alunos_media = 0
        alunos_std = 1

    scatter = ax.scatter(alunos, tempos, alpha=0.6, s=100, c=tempos, cmap='RdYlGn', 
                        edgecolors='black', linewidth=0.5)

    for i, (t, a, n) in enumerate(zip(tempos, alunos, nomes)):
        if len(tempos) > 2:
            if abs(t - tempo_media) > 1.5 * tempo_std or abs(a - alunos_media) > 1.5 * alunos_std:
                ax.annotate(n[:20], (a, t), xytext=(5, 5), textcoords='offset points', 
                           fontsize=7, alpha=0.8, bbox=dict(boxstyle='round,pad=0.3', 
                           facecolor='yellow', alpha=0.7))

    ax.set_xlabel('Número de Alunos Avaliados', fontsize=11, fontweight='bold')
    ax.set_ylabel('Tempo Total de Dedicação (horas)', fontsize=11, fontweight='bold')
    ax.set_title('Relação: Tempo de Dedicação vs Alunos Avaliados por Professor', 
                fontsize=13, fontweight='bold', pad=15)

    if len(alunos) > 1 and max(alunos) > 0:
        z = np.polyfit(alunos, tempos, 1)
        p = np.poly1d(z)
        x_tend = np.linspace(min(alunos), max(alunos), 100)
        ax.plot(x_tend, p(x_tend), "r--", alpha=0.5, linewidth=1.5, label='Tendência')
        ax.legend(fontsize=9)

    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Tempo Total (horas)', fontsize=9)

    ax.grid(alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buffer.seek(0)
    return buffer


# ============================================================================
# FUNÇÃO PRINCIPAL DO PDF
# ============================================================================

def criar_pdf(dados, municipio, segmentos_disponiveis, tipo_relatorio='completo'):
    """Cria o PDF do relatório"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           topMargin=1.5*cm, bottomMargin=1.5*cm,
                           leftMargin=1.5*cm, rightMargin=1.5*cm)

    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.HexColor('#2C3E50'),
        alignment=1,
        spaceAfter=20,
        fontName=FONT_NAME
    )

    estilo_subtitulo = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12,
        spaceBefore=12,
        fontName=FONT_NAME
    )

    estilo_normal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=6,
        fontName=FONT_NAME,
        wordWrap='CJK'
    )

    estilo_celula = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=1,
        fontName=FONT_NAME,
        wordWrap='CJK'
    )

    estilo_celula_header = ParagraphStyle(
        'CellHeaderStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.white,
        fontName=FONT_NAME,
        wordWrap='CJK'
    )

    def format_valor(valor, formato='.1f', padrao='N/A'):
        if valor is None:
            return padrao
        try:
            return f"{valor:{formato}}"
        except (TypeError, ValueError):
            return str(valor)

    story = []

    # Título
    story.append(Paragraph(f"RELATÓRIO DE ANÁLISE DE AVALIAÇÕES", estilo_titulo))
    story.append(Paragraph(f"Município: {municipio}", estilo_normal))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", estilo_normal))
    story.append(Spacer(1, 15))

    # ===== 1. RESUMO EXECUTIVO =====
    story.append(Paragraph("1. RESUMO EXECUTIVO", estilo_subtitulo))

    resumo_data = [[Paragraph('Indicador', estilo_celula_header)]]

    if segmentos_disponiveis['infantil']:
        resumo_data[0].append(Paragraph('Educação Infantil', estilo_celula_header))
    if segmentos_disponiveis['fundamental']:
        resumo_data[0].append(Paragraph('Ensino Fundamental', estilo_celula_header))

    if dados['infantil']:
        resumo_data.append([
            Paragraph('Alunos Avaliados', estilo_celula),
            Paragraph(str(len(dados['infantil']['tempos'])), estilo_celula)
        ])
        if dados['infantil']['tempos']:
            resumo_data.append([
                Paragraph('Tempo Médio (min)', estilo_celula),
                Paragraph(format_valor(np.mean(dados['infantil']['tempos'])), estilo_celula)
            ])
            resumo_data.append([
                Paragraph('Tempo Médio (h)', estilo_celula),
                Paragraph(format_valor(np.mean(dados['infantil']['tempos'])/60), estilo_celula)
            ])

    if dados['fundamental']:
        if not dados['infantil']:
            resumo_data.append([Paragraph('Alunos Avaliados', estilo_celula)])
            resumo_data[-1].append(Paragraph(str(len(dados['fundamental']['tempos'])), estilo_celula))
        else:
            if len(resumo_data) > 1:
                resumo_data[1].append(Paragraph(str(len(dados['fundamental']['tempos'])), estilo_celula))
            else:
                resumo_data.append([Paragraph('Alunos Avaliados', estilo_celula), Paragraph('', estilo_celula)])
                resumo_data[-1].append(Paragraph(str(len(dados['fundamental']['tempos'])), estilo_celula))

        if dados['fundamental']['tempos']:
            if not dados['infantil']:
                resumo_data.append([Paragraph('Tempo Médio (min)', estilo_celula)])
                resumo_data[-1].append(Paragraph(format_valor(np.mean(dados['fundamental']['tempos'])), estilo_celula))
                resumo_data.append([Paragraph('Tempo Médio (h)', estilo_celula)])
                resumo_data[-1].append(Paragraph(format_valor(np.mean(dados['fundamental']['tempos'])/60), estilo_celula))
            else:
                if len(resumo_data) > 2:
                    resumo_data[2].append(Paragraph(format_valor(np.mean(dados['fundamental']['tempos'])), estilo_celula))
                if len(resumo_data) > 3:
                    resumo_data[3].append(Paragraph(format_valor(np.mean(dados['fundamental']['tempos'])/60), estilo_celula))

    col_widths = [5.5*cm] + [4.5*cm] * (len(resumo_data[0])-1)
    tabela = Table(resumo_data, colWidths=col_widths)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8F9FA'), colors.white]),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 15))

    # ===== 2. ALUNOS AVALIADOS POR SEGMENTO =====
    if segmentos_disponiveis['infantil'] or segmentos_disponiveis['fundamental']:
        story.append(Paragraph("2. ALUNOS AVALIADOS POR SEGMENTO", estilo_subtitulo))

        img_buffer = criar_grafico_barras_alunos(
            dados['infantil'] if dados['infantil'] else None,
            dados['fundamental'] if dados['fundamental'] else None
        )
        if img_buffer:
            imagem = Image(img_buffer, width=14*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

    # ===== 3. ESCOLAS QUE REALIZARAM AVALIAÇÕES =====
    escolas_infantil = dados['infantil']['escolas'] if dados['infantil'] else {}
    escolas_fundamental = dados['fundamental']['escolas'] if dados['fundamental'] else {}

    if escolas_infantil or escolas_fundamental:
        story.append(PageBreak())
        story.append(Paragraph("3. MAPA DAS ESCOLAS COM AVALIAÇÕES REALIZADAS", estilo_subtitulo))

        img_buffer = criar_grafico_escolas_avaliadas(escolas_infantil, escolas_fundamental)
        if img_buffer:
            imagem = Image(img_buffer, width=16*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

        todas_escolas = list(set(escolas_infantil.keys()) | set(escolas_fundamental.keys()))
        if todas_escolas:
            story.append(Paragraph("<b>Relação de Escolas que Realizaram Avaliações:</b>", estilo_normal))
            for escola in sorted(todas_escolas):
                total_infantil = escolas_infantil.get(escola, {}).get('total_alunos', 0)
                total_fundamental = escolas_fundamental.get(escola, {}).get('total_alunos', 0)
                story.append(Paragraph(f"• {escola}: {total_infantil} alunos (Infantil) + {total_fundamental} alunos (Fundamental) = {total_infantil + total_fundamental} total", estilo_normal))

        story.append(Spacer(1, 15))

    # ===== 4. MAPA DE CALOR - ESCOLAS E ESTÁGIOS =====
    if dados['infantil'] and dados['infantil']['escolas']:
        story.append(PageBreak())
        story.append(Paragraph("4. MAPA DE CALOR - DISTRIBUIÇÃO DE ESTÁGIOS POR ESCOLA", estilo_subtitulo))
        story.append(Paragraph("<b>Educação Infantil:</b>", estilo_normal))
        story.append(Spacer(1, 5))

        img_buffer = criar_heatmap_escolas_estagios(
            dados['infantil']['escolas'],
            "Distribuição de Estágios por Escola - Educação Infantil"
        )
        if img_buffer:
            imagem = Image(img_buffer, width=16*cm, height=max(8, len(dados['infantil']['escolas']) * 0.6)*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

    if dados['fundamental'] and dados['fundamental']['escolas']:
        story.append(PageBreak())
        story.append(Paragraph("<b>Ensino Fundamental:</b>", estilo_normal))
        story.append(Spacer(1, 5))

        img_buffer = criar_heatmap_escolas_estagios(
            dados['fundamental']['escolas'],
            "Distribuição de Estágios por Escola - Ensino Fundamental"
        )
        if img_buffer:
            imagem = Image(img_buffer, width=16*cm, height=max(8, len(dados['fundamental']['escolas']) * 0.6)*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

    # ===== 5. TEMPO MÉDIO DE AVALIAÇÃO =====
    if dados['infantil'] or dados['fundamental']:
        story.append(PageBreak())
        story.append(Paragraph("5. TEMPO MÉDIO DE AVALIAÇÃO POR ALUNO", estilo_subtitulo))

        img_buffer = criar_grafico_barras_tempo(
            dados['infantil'] if dados['infantil'] else None,
            dados['fundamental'] if dados['fundamental'] else None
        )
        if img_buffer:
            imagem = Image(img_buffer, width=14*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

    # ===== 6. DISTRIBUIÇÃO DOS TEMPOS =====
    tempos_infantil = dados['infantil']['tempos'] if dados['infantil'] else []
    tempos_fundamental = dados['fundamental']['tempos'] if dados['fundamental'] else []

    if tempos_infantil or tempos_fundamental:
        story.append(PageBreak())
        story.append(Paragraph("6. DISTRIBUIÇÃO DOS TEMPOS DE AVALIAÇÃO", estilo_subtitulo))

        img_buffer = criar_histograma(tempos_infantil, tempos_fundamental)
        if img_buffer:
            imagem = Image(img_buffer, width=16*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)

    # Se for versão reduzida, finaliza aqui
    if tipo_relatorio == 'reduzido':
        story.append(Spacer(1, 15))
        story.append(PageBreak())
        story.append(Paragraph("7. CONCLUSÕES E RECOMENDAÇÕES", estilo_subtitulo))

        story.append(Paragraph(f"• Total de alunos avaliados no sistema: <b>{dados['horarios']['total_alunos']} alunos</b>", estilo_normal))

        todas_escolas = list(set(escolas_infantil.keys()) | set(escolas_fundamental.keys()))
        story.append(Paragraph(f"• Total de escolas que realizaram avaliações: <b>{len(todas_escolas)} escolas</b>", estilo_normal))

        if dados['infantil'] and dados['fundamental']:
            if len(dados['infantil']['tempos']) > len(dados['fundamental']['tempos']):
                story.append(Paragraph(f"• Maior participação da Educação Infantil: {len(dados['infantil']['tempos'])} alunos ({len(dados['infantil']['tempos'])/dados['horarios']['total_alunos']*100:.1f}% do total)", estilo_normal))
            else:
                story.append(Paragraph(f"• Maior participação do Ensino Fundamental: {len(dados['fundamental']['tempos'])} alunos ({len(dados['fundamental']['tempos'])/dados['horarios']['total_alunos']*100:.1f}% do total)", estilo_normal))

        story.append(Spacer(1, 25))
        story.append(Paragraph(f"<i>Relatório de acompanhamento das avaliações - {municipio}</i>", 
                              ParagraphStyle('Footer', parent=styles['Italic'], fontSize=8, alignment=1, fontName=FONT_NAME)))

        doc.build(story)
        buffer.seek(0)
        return buffer

    # ===== CONTINUA PARA RELATÓRIO COMPLETO =====

    # ===== 7. ANÁLISE DE OUTLIERS =====
    story.append(PageBreak())
    story.append(Paragraph("7. ANÁLISE DE TEMPOS ATÍPICOS (OUTLIERS)", estilo_subtitulo))

    if dados['infantil'] and dados['infantil']['tempos']:
        outliers_infantil = detectar_outliers(dados['infantil']['tempos'])

        story.append(Paragraph("<b>Educação Infantil:</b>", estilo_normal))
        story.append(Paragraph(f"• Média: {format_valor(np.mean(dados['infantil']['tempos']))} min | Mediana: {format_valor(np.median(dados['infantil']['tempos']))} min", estilo_normal))
        story.append(Paragraph(f"• Q1: {format_valor(outliers_infantil['q1'])} min | Q3: {format_valor(outliers_infantil['q3'])} min", estilo_normal))
        story.append(Paragraph(f"• Limite inferior: {format_valor(outliers_infantil['limite_inferior'])} min | Limite superior: {format_valor(outliers_infantil['limite_superior'])} min", estilo_normal))
        story.append(Paragraph(f"• Alunos com tempos atípicos: <b>{len(outliers_infantil['outliers'])}</b>", 
                              ParagraphStyle('Alert', parent=estilo_normal, textColor=colors.HexColor('#C0392B'))))

        story.append(Spacer(1, 10))
        img_buffer = criar_grafico_outliers(dados['infantil']['tempos'], outliers_infantil, "Análise de Outliers - Educação Infantil")
        if img_buffer:
            imagem = Image(img_buffer, width=15*cm, height=7*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
        story.append(Spacer(1, 15))

    if dados['fundamental'] and dados['fundamental']['tempos']:
        outliers_fundamental = detectar_outliers(dados['fundamental']['tempos'])

        story.append(Paragraph("<b>Ensino Fundamental:</b>", estilo_normal))
        story.append(Paragraph(f"• Média: {format_valor(np.mean(dados['fundamental']['tempos']))} min | Mediana: {format_valor(np.median(dados['fundamental']['tempos']))} min", estilo_normal))
        story.append(Paragraph(f"• Q1: {format_valor(outliers_fundamental['q1'])} min | Q3: {format_valor(outliers_fundamental['q3'])} min", estilo_normal))
        story.append(Paragraph(f"• Limite inferior: {format_valor(outliers_fundamental['limite_inferior'])} min | Limite superior: {format_valor(outliers_fundamental['limite_superior'])} min", estilo_normal))
        story.append(Paragraph(f"• Alunos com tempos atípicos: <b>{len(outliers_fundamental['outliers'])}</b>", 
                              ParagraphStyle('Alert', parent=estilo_normal, textColor=colors.HexColor('#C0392B'))))

        story.append(Spacer(1, 10))
        img_buffer = criar_grafico_outliers(dados['fundamental']['tempos'], outliers_fundamental, "Análise de Outliers - Ensino Fundamental")
        if img_buffer:
            imagem = Image(img_buffer, width=15*cm, height=7*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)

    # ===== 8. ANÁLISE DE HORÁRIOS =====
    if dados['horarios']:
        story.append(PageBreak())
        story.append(Paragraph("8. ANÁLISE DE HORÁRIOS DE FINALIZAÇÃO", estilo_subtitulo))

        total_alunos = dados['horarios']['total_alunos']
        story.append(Paragraph(f"Total de alunos avaliados: <b>{total_alunos}</b>", estilo_normal))

        if dados['horarios']['horas']:
            hora_pico = max(dados['horarios']['horas'], key=dados['horarios']['horas'].get)
            percentual = (dados['horarios']['horas'][hora_pico] / total_alunos) * 100 if total_alunos > 0 else 0
            story.append(Paragraph(f"Horário de pico de finalizações: <b>{hora_pico}:00h</b> ({dados['horarios']['horas'][hora_pico]} alunos - {percentual:.1f}% do total)", estilo_normal))

        story.append(Spacer(1, 10))

        img_buffer = criar_grafico_horarios_alunos(dados['horarios']['horas'], total_alunos)
        if img_buffer:
            imagem = Image(img_buffer, width=15*cm, height=7*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 15))

        story.append(Paragraph("<b>Distribuição por Horário e Dia da Semana</b>", estilo_normal))
        story.append(Spacer(1, 5))

        img_buffer = criar_heatmap_alunos(dados['horarios']['hora_dia'])
        if img_buffer:
            imagem = Image(img_buffer, width=14*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 15))

    # ===== 9. ANÁLISE DE DEDICAÇÃO DOS PROFESSORES =====
    if dados['professores']['todos']:
        story.append(PageBreak())
        story.append(Paragraph("9. ANÁLISE DE DEDICAÇÃO DOS PROFESSORES", estilo_subtitulo))

        total_professores = len(dados['professores']['todos'])
        story.append(Paragraph(f"<b>Total de professores que realizaram avaliações: {total_professores}</b>", estilo_normal))

        tempos_professores = [p['tempo_total_horas'] for p in dados['professores']['todos'].values()]
        if tempos_professores:
            tempo_medio_prof = np.mean(tempos_professores)
            tempo_total_prof = np.sum(tempos_professores)
            story.append(Paragraph(f"• Tempo total de dedicação de todos os professores: <b>{format_valor(tempo_total_prof)} horas</b>", estilo_normal))
            story.append(Paragraph(f"• Tempo médio de dedicação por professor: <b>{format_valor(tempo_medio_prof)} horas</b>", estilo_normal))

        story.append(Spacer(1, 10))

        story.append(Paragraph("<b>Top 15 Professores com Maior Tempo de Dedicação:</b>", estilo_normal))
        story.append(Spacer(1, 5))

        img_buffer = criar_grafico_professores(dados['professores']['todos'])
        if img_buffer:
            imagem = Image(img_buffer, width=16*cm, height=10*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

        story.append(Paragraph("<b>Relação entre Tempo de Dedicação e Número de Alunos:</b>", estilo_normal))
        story.append(Spacer(1, 5))

        img_buffer = criar_grafico_dispersao_professores(dados['professores']['todos'])
        if img_buffer:
            imagem = Image(img_buffer, width=15*cm, height=8*cm)
            imagem.hAlign = 'CENTER'
            story.append(imagem)
            story.append(Spacer(1, 10))

        story.append(PageBreak())
        story.append(Paragraph("<b>Detalhamento de Tempo de Dedicação por Professor:</b>", estilo_normal))
        story.append(Spacer(1, 5))

        professores_ordenados = sorted(dados['professores']['todos'].items(), 
                                      key=lambda x: x[1].get('tempo_total_horas', 0), reverse=True)

        prof_data = [
            [Paragraph('Professor', estilo_celula_header),
             Paragraph('Escola', estilo_celula_header),
             Paragraph('Segmento', estilo_celula_header),
             Paragraph('Alunos', estilo_celula_header),
             Paragraph('Tempo Total (h)', estilo_celula_header),
             Paragraph('Tempo Médio/Aluno (min)', estilo_celula_header)]
        ]

        for prof_id, dados_prof in professores_ordenados[:50]:
            nome = dados_prof.get('nome', f'Professor {prof_id[:8]}')
            escola = dados_prof.get('escola', 'N/A')
            segmento = dados_prof.get('segmento', 'ambos')
            if segmento == 'infantil':
                segmento_texto = 'Educação Infantil'
            elif segmento == 'fundamental':
                segmento_texto = 'Ensino Fundamental'
            else:
                segmento_texto = 'Ambos'

            alunos = dados_prof.get('total_alunos', 0)
            tempo_horas = dados_prof.get('tempo_total_horas', 0)
            tempo_medio_aluno = (dados_prof.get('tempo_total_minutos', 0) / alunos) if alunos > 0 else 0

            prof_data.append([
                Paragraph(nome[:30], estilo_celula),
                Paragraph(escola[:25], estilo_celula),
                Paragraph(segmento_texto, estilo_celula),
                Paragraph(str(alunos), estilo_celula),
                Paragraph(format_valor(tempo_horas), estilo_celula),
                Paragraph(format_valor(tempo_medio_aluno), estilo_celula)
            ])

        col_widths = [4*cm, 3*cm, 2.5*cm, 1.5*cm, 2*cm, 2.5*cm]

        tabela_prof = Table(prof_data, colWidths=col_widths, repeatRows=1)
        tabela_prof.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8F9FA'), colors.white]),
        ]))
        story.append(tabela_prof)

        professores_com_outliers = [
            (prof_id, dados_prof) for prof_id, dados_prof in professores_ordenados 
            if dados_prof.get('alunos_outliers')
        ]

        if professores_com_outliers:
            story.append(Spacer(1, 15))
            story.append(Paragraph("<b>Professores com Alunos em Tempos Atípicos:</b>", 
                                  ParagraphStyle('AlertTitle', parent=estilo_normal, textColor=colors.HexColor('#C0392B'), fontName=FONT_NAME)))
            story.append(Spacer(1, 5))

            for prof_id, dados_prof in professores_com_outliers[:10]:
                story.append(Paragraph(f"• <b>{dados_prof.get('nome', f'Professor {prof_id[:8]}')}</b> - {len(dados_prof.get('alunos_outliers', []))} aluno(s) com tempo atípico:", estilo_normal))
                for aluno_out in dados_prof.get('alunos_outliers', [])[:3]:
                    tempos_array = np.array(dados_prof.get('alunos_tempos', [0]))
                    if len(tempos_array) > 0:
                        q1 = np.percentile(tempos_array, 25)
                        classificacao = "MUITO RÁPIDO" if aluno_out.get('tempo_minutos', 0) < q1 else "MUITO LONGO"
                    else:
                        classificacao = "ATÍPICO"
                    story.append(Paragraph(f"  - Aluno {aluno_out.get('aluno', 'N/A')}: {format_valor(aluno_out.get('tempo_minutos'))} min ({classificacao})", 
                                          ParagraphStyle('AlertText', parent=estilo_normal, textColor=colors.HexColor('#E74C3C'), fontSize=9, fontName=FONT_NAME)))

    # ===== 10. CONCLUSÕES =====
    story.append(PageBreak())
    story.append(Paragraph("10. CONCLUSÕES E RECOMENDAÇÕES", estilo_subtitulo))

    story.append(Paragraph(f"• Total de alunos avaliados no sistema: <b>{dados['horarios']['total_alunos']} alunos</b>", estilo_normal))

    todas_escolas = list(set(escolas_infantil.keys()) | set(escolas_fundamental.keys()))
    story.append(Paragraph(f"• Total de escolas que realizaram avaliações: <b>{len(todas_escolas)} escolas</b>", estilo_normal))

    if dados['professores']['todos']:
        story.append(Paragraph(f"• Total de professores envolvidos: <b>{len(dados['professores']['todos'])} professores</b>", estilo_normal))

    if dados['infantil'] and dados['fundamental']:
        total_inf = len(dados['infantil']['tempos'])
        total_fund = len(dados['fundamental']['tempos'])
        if total_inf > total_fund:
            story.append(Paragraph(f"• Maior participação da Educação Infantil: {total_inf} alunos ({total_inf/dados['horarios']['total_alunos']*100:.1f}% do total)", estilo_normal))
        else:
            story.append(Paragraph(f"• Maior participação do Ensino Fundamental: {total_fund} alunos ({total_fund/dados['horarios']['total_alunos']*100:.1f}% do total)", estilo_normal))

    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<i>Relatório de acompanhamento das avaliações - {municipio}</i>", 
                          ParagraphStyle('Footer', parent=styles['Italic'], fontSize=8, alignment=1, fontName=FONT_NAME)))

    doc.build(story)
    buffer.seek(0)
    return buffer
