# advanced_analytics.py - VERSÃO CORRIGIDA (com 11 dias e HAVING fix)

# -*- coding: utf-8 -*-
"""
Módulo de análises avançadas para relatórios
Implementa análises preditivas e prescritivas - Versão PostgreSQL
"""

from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


@dataclass
class RiscoAtraso:
    """Estrutura para dados de risco de atraso"""
    escola: str
    score: int
    nivel: str
    progresso_atual: float
    previsao_conclusao: str
    fatores_contribuintes: List[str]
    acao_recomendada: str
    horas_extras_necessarias: float
    cor: str


@dataclass
class CargaProfessor:
    """Estrutura para dados de carga de trabalho do professor"""
    professor_id: str
    professor_nome: str
    escola: str
    alunos_dia: float
    horas_dia: float
    capacidade_maxima: float
    classificacao: str
    recomendacao: str
    alunos_redistribuir: int
    cor: str


@dataclass
class PrevisaoDemanda:
    """Estrutura para previsão de demanda diária"""
    dia_semana: str
    data: str
    previsao_avaliacoes: float
    limite_superior: float
    limite_inferior: float
    classificacao: str
    recomendacao: str


@dataclass
class CurvaAprendizado:
    """Estrutura para curva de aprendizado do professor"""
    professor_id: str
    nome: str
    tendencia: str
    velocidade_melhoria: float
    variacao_percentual: float
    recomendacao: str
    cor: str
    alerta_queda_brusca: bool


@dataclass
class MatrizQuadrante:
    """Estrutura para matriz 4 quadrantes"""
    escola: str
    eficiencia: float
    eficacia: float
    quadrante: str
    cor: str
    acao_recomendada: str


class AdvancedAnalytics:
    """Classe para análises avançadas - PostgreSQL"""
    
    # Período padrão para análises (11 dias)
    DIAS_ANALISE = 11
    
    def __init__(self, db):
        self.db = db
        
    def get_db_connection(self):
        return self.db.get_connection()
    
    # ========== 1. SCORING DE RISCO DE ATRASO ==========
    
    def calcular_score_risco_atraso(self, escola_nome: str, dados_escola: dict, 
                                     data_limite: datetime = None) -> RiscoAtraso:
        """Calcula score de risco de atraso para uma escola (0-100)"""
        if data_limite is None:
            data_limite = datetime.now() + timedelta(days=30)
        
        score = 0
        fatores = []
        hoje = datetime.now()
        
        dias_restantes = (data_limite - hoje).days
        if dias_restantes <= 0:
            score += 50
            fatores.append("Prazo já expirado")
        
        # Fator 1: Taxa de progresso atual (0-35 pontos)
        alunos_totais = dados_escola.get('alunos_totais', 1)
        alunos_avaliados = dados_escola.get('alunos_avaliados', 0)
        percentual_concluido = (alunos_avaliados / alunos_totais) * 100 if alunos_totais > 0 else 0
        
        alunos_faltantes = alunos_totais - alunos_avaliados
        taxa_necessaria_diaria = alunos_faltantes / max(dias_restantes, 1)
        taxa_historica = self._calcular_taxa_progresso_historica(escola_nome, dias=self.DIAS_ANALISE)
        
        if taxa_historica > 0 and taxa_necessaria_diaria > 0:
            fator_progresso = (taxa_historica / taxa_necessaria_diaria)
            if fator_progresso < 0.5:
                score += 35
                fatores.append(f"Progresso muito abaixo da meta (atual: {taxa_historica:.1f}/dia, necessário: {taxa_necessaria_diaria:.1f}/dia)")
            elif fator_progresso < 0.8:
                score += 20
                fatores.append(f"Progresso abaixo da meta")
        
        # Fator 2: Professores com baixa eficiência (0-25 pontos)
        professores_ineficientes = self._contar_professores_ineficientes(escola_nome)
        total_professores = self._total_professores_escola(escola_nome)
        
        if total_professores > 0:
            proporcao_ineficientes = professores_ineficientes / total_professores
            if proporcao_ineficientes > 0.5:
                score += 25
                fatores.append(f"{professores_ineficientes} de {total_professores} professores abaixo da eficiência esperada")
            elif proporcao_ineficientes > 0.3:
                score += 15
                fatores.append(f"{professores_ineficientes} professores com eficiência abaixo do esperado")
        
        # Fator 3: Professores sobrecarregados (0-20 pontos)
        professores_sobrecarregados = self._contar_professores_sobrecarregados(escola_nome)
        if professores_sobrecarregados > 0:
            score += min(20, professores_sobrecarregados * 7)
            fatores.append(f"{professores_sobrecarregados} professor(es) sobrecarregado(s)")
        
        # Fator 4: Percentual já concluído (0-20 pontos - bônus)
        if percentual_concluido > 80:
            score -= 15
        elif percentual_concluido < 30:
            score += 15
        
        # Definir nível e ação recomendada
        if score >= 70:
            nivel = "CRÍTICO"
            acao = "INTERVENÇÃO URGENTE - Alocar equipe de apoio extra imediatamente"
            horas_extras = alunos_faltantes * 0.1
            cor = '#E74C3C'
        elif score >= 50:
            nivel = "ALTO"
            acao = "INTERVENÇÃO PRIORITÁRIA - Reunião com direção e reforço pedagógico"
            horas_extras = alunos_faltantes * 0.05
            cor = '#E67E22'
        elif score >= 30:
            nivel = "MÉDIO"
            acao = "Monitoramento reforçado - Acompanhamento semanal"
            horas_extras = alunos_faltantes * 0.02
            cor = '#F39C12'
        else:
            nivel = "BAIXO"
            acao = "Manter cronograma atual"
            horas_extras = 0
            cor = '#27AE60'
        
        data_prevista = self._prever_data_conclusao(escola_nome, alunos_faltantes, taxa_historica if taxa_historica > 0 else 10)
        data_prevista_str = data_prevista.strftime('%d/%m/%Y') if data_prevista else 'N/A'
        
        return RiscoAtraso(
            escola=escola_nome,
            score=score,
            nivel=nivel,
            progresso_atual=percentual_concluido,
            previsao_conclusao=data_prevista_str,
            fatores_contribuintes=fatores,
            acao_recomendada=acao,
            horas_extras_necessarias=horas_extras,
            cor=cor
        )
    
    def _calcular_taxa_progresso_historica(self, escola_nome: str, dias: int = None) -> float:
        """Calcula taxa média de alunos avaliados por dia nos últimos N dias - PostgreSQL"""
        if dias is None:
            dias = self.DIAS_ANALISE
            
        conn = self.get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        try:
            query = f"""
                SELECT COUNT(DISTINCT av.aluno_matricula)::float / {dias} as taxa_diaria
                FROM avaliacoes_habilidades av
                LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN escolas e ON t.escola_id = e.id
                WHERE e.nome = %s 
                  AND av.fim_avaliacao >= CURRENT_DATE - INTERVAL '{dias} days'
            """
            cursor.execute(query, (escola_nome,))
            resultado = cursor.fetchone()
            return float(resultado[0]) if resultado and resultado[0] else 0.0
        except Exception as e:
            print(f"Erro ao calcular taxa progresso: {e}")
            return 0.0
        finally:
            cursor.close()
            conn.close()
    
    def _contar_professores_ineficientes(self, escola_nome: str) -> int:
        """Conta professores com eficiência abaixo do esperado na escola"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        try:
            query = """
                SELECT COUNT(DISTINCT av.avaliador_id)
                FROM avaliacoes_habilidades av
                LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN escolas e ON t.escola_id = e.id
                WHERE e.nome = %s AND av.avaliador_id IS NOT NULL
            """
            cursor.execute(query, (escola_nome,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else 0
        except Exception as e:
            print(f"Erro ao contar professores ineficientes: {e}")
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def _total_professores_escola(self, escola_nome: str) -> int:
        """Total de professores na escola"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        try:
            query = """
                SELECT COUNT(DISTINCT av.avaliador_id)
                FROM avaliacoes_habilidades av
                LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN escolas e ON t.escola_id = e.id
                WHERE e.nome = %s AND av.avaliador_id IS NOT NULL
            """
            cursor.execute(query, (escola_nome,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else 0
        except Exception as e:
            print(f"Erro ao total professores: {e}")
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def _contar_professores_sobrecarregados(self, escola_nome: str) -> int:
        """Conta professores sobrecarregados (mais de 25 alunos por dia em média)"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        try:
            # CORREÇÃO: Não usar alias no HAVING, repetir a expressão
            query = f"""
                SELECT av.avaliador_id,
                       COUNT(DISTINCT DATE(av.fim_avaliacao)) as dias,
                       COUNT(*) as total_alunos
                FROM avaliacoes_habilidades av
                LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN escolas e ON t.escola_id = e.id
                WHERE e.nome = %s 
                  AND av.avaliador_id IS NOT NULL
                  AND av.fim_avaliacao >= CURRENT_DATE - INTERVAL '{self.DIAS_ANALISE} days'
                GROUP BY av.avaliador_id
                HAVING COUNT(*)::float / COUNT(DISTINCT DATE(av.fim_avaliacao)) > 25
            """
            cursor.execute(query, (escola_nome,))
            resultado = cursor.fetchall()
            return len(resultado) if resultado else 0
        except Exception as e:
            print(f"Erro ao contar professores sobrecarregados: {e}")
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def _prever_data_conclusao(self, escola_nome: str, alunos_faltantes: int, taxa_historica: float) -> datetime:
        """Prevê data de conclusão baseada no ritmo atual"""
        if taxa_historica <= 0:
            taxa_historica = 10
        dias_necessarios = alunos_faltantes / taxa_historica
        return datetime.now() + timedelta(days=dias_necessarios)
    
    # ========== 2. ANÁLISE DE CARGA DE TRABALHO DOS PROFESSORES ==========
    
    def analisar_carga_trabalho_professor(self, professor_id: str) -> Optional[CargaProfessor]:
        """Analisa a carga de trabalho de um professor específico - PostgreSQL"""
        conn = self.get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        
        try:
            query = f"""
                SELECT 
                    COALESCE(p.nome, 'Professor') as nome,
                    COALESCE(e.nome, 'Sem escola') as escola_nome,
                    COUNT(DISTINCT av.aluno_matricula) as total_alunos,
                    COUNT(DISTINCT DATE(av.fim_avaliacao)) as dias_trabalhados,
                    COALESCE(SUM(EXTRACT(EPOCH FROM (av.fim_avaliacao - av.inicio_avaliacao))) / 3600.0, 0) as horas_totais
                FROM avaliacoes_habilidades av
                LEFT JOIN professores p ON av.avaliador_id = p.id_plurall
                LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN escolas e ON t.escola_id = e.id
                WHERE av.avaliador_id = %s 
                  AND av.fim_avaliacao >= CURRENT_DATE - INTERVAL '{self.DIAS_ANALISE} days'
                GROUP BY p.nome, e.nome
            """
            cursor.execute(query, (str(professor_id),))
            resultado = cursor.fetchone()
            
            if not resultado or resultado[2] == 0:
                return None
            
            nome = resultado[0] if resultado[0] else f"Professor {professor_id[:8]}"
            escola = resultado[1] if resultado[1] else "Sem escola"
            total_alunos = resultado[2]
            dias_trabalhados = max(resultado[3], 1)
            horas_totais = resultado[4] if resultado[4] else 0
            
            alunos_por_dia = total_alunos / dias_trabalhados
            
            if alunos_por_dia > 40:
                classificacao = "CRÍTICO"
                recomendacao = "REDISTRIBUIR IMEDIATAMENTE"
                alunos_redistribuir = int(alunos_por_dia - 25)
                cor = '#E74C3C'
            elif alunos_por_dia > 30:
                classificacao = "ALTO"
                recomendacao = "Redistribuir alunos"
                alunos_redistribuir = int(alunos_por_dia - 25)
                cor = '#E67E22'
            elif alunos_por_dia > 20:
                classificacao = "MODERADO"
                recomendacao = "Monitorar carga"
                alunos_redistribuir = 0
                cor = '#F39C12'
            else:
                classificacao = "NORMAL"
                recomendacao = "Manter carga atual"
                alunos_redistribuir = 0
                cor = '#27AE60'
            
            return CargaProfessor(
                professor_id=str(professor_id),
                professor_nome=nome,
                escola=escola,
                alunos_dia=round(alunos_por_dia, 1),
                horas_dia=round(horas_totais / dias_trabalhados, 1),
                capacidade_maxima=25.0,
                classificacao=classificacao,
                recomendacao=recomendacao,
                alunos_redistribuir=alunos_redistribuir,
                cor=cor
            )
        except Exception as e:
            print(f"Erro ao analisar carga do professor {professor_id}: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    # ========== 3. ANÁLISE DE CURVA DE APRENDIZADO ==========
    
    def analisar_curva_aprendizado(self, professor_id: str) -> Optional[CurvaAprendizado]:
        """Analisa se o professor está melhorando ou piorando ao longo do tempo - PostgreSQL"""
        conn = self.get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        
        try:
            query = f"""
                SELECT 
                    EXTRACT(WEEK FROM av.fim_avaliacao) as semana,
                    COUNT(*) as total_alunos,
                    AVG(EXTRACT(EPOCH FROM (av.fim_avaliacao - av.inicio_avaliacao))) / 60.0 as tempo_medio_minutos
                FROM avaliacoes_habilidades av
                WHERE av.avaliador_id = %s 
                  AND av.fim_avaliacao >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY EXTRACT(WEEK FROM av.fim_avaliacao)
                ORDER BY semana
            """
            cursor.execute(query, (str(professor_id),))
            dados = cursor.fetchall()
            
            if len(dados) < 3:
                return None
            
            # Obter nome do professor
            cursor.execute("SELECT nome FROM professores WHERE id_plurall = %s", (str(professor_id),))
            nome_result = cursor.fetchone()
            nome = nome_result[0] if nome_result else f"Professor {professor_id[:8]}"
            
            semanas = list(range(len(dados)))
            tempos = [float(row[2]) for row in dados]
            
            slope, intercept, r_value, p_value, std_err = stats.linregress(semanas, tempos)
            
            if slope < -1.0:
                tendencia = "MELHORANDO_RAPIDAMENTE"
                recomendacao = "Parabenizar e compartilhar boas práticas"
                cor = '#27AE60'
                alerta = False
            elif slope < -0.3:
                tendencia = "MELHORANDO"
                recomendacao = "Manter direção atual"
                cor = '#2ECC71'
                alerta = False
            elif slope < 0.3:
                tendencia = "ESTAVEL"
                recomendacao = "Monitorar para evitar piora"
                cor = '#3498DB'
                alerta = False
            elif slope < 1.0:
                tendencia = "PIORANDO"
                recomendacao = "Orientar sobre otimização do processo"
                cor = '#F39C12'
                alerta = True
            else:
                tendencia = "PIORANDO_RAPIDAMENTE"
                recomendacao = "INTERVENÇÃO URGENTE - Capacitação necessária"
                cor = '#E74C3C'
                alerta = True
            
            variacao = ((tempos[-1] - tempos[0]) / tempos[0]) * 100 if tempos[0] > 0 else 0
            
            return CurvaAprendizado(
                professor_id=str(professor_id),
                nome=nome,
                tendencia=tendencia,
                velocidade_melhoria=abs(slope),
                variacao_percentual=variacao,
                recomendacao=recomendacao,
                cor=cor,
                alerta_queda_brusca=alerta and variacao > 10
            )
        except Exception as e:
            print(f"Erro ao analisar curva do professor {professor_id}: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    # ========== 4. PREVISÃO DE DEMANDA ==========
    
    def prever_demanda_proxima_semana(self, escola_nome: str = None) -> List[PrevisaoDemanda]:
        """Previsão de demanda para os próximos 7 dias - PostgreSQL"""
        conn = self.get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        
        try:
            if escola_nome:
                query = f"""
                    SELECT EXTRACT(DOW FROM av.fim_avaliacao) as dia_semana, COUNT(*) as total_alunos
                    FROM avaliacoes_habilidades av
                    LEFT JOIN alunos a ON av.aluno_matricula = a.matricula
                    LEFT JOIN turmas t ON a.turma_id = t.id
                    LEFT JOIN escolas e ON t.escola_id = e.id
                    WHERE av.fim_avaliacao >= CURRENT_DATE - INTERVAL '{self.DIAS_ANALISE} days'
                      AND e.nome = %s
                    GROUP BY EXTRACT(DOW FROM av.fim_avaliacao)
                """
                cursor.execute(query, (escola_nome,))
            else:
                query = f"""
                    SELECT EXTRACT(DOW FROM av.fim_avaliacao) as dia_semana, COUNT(*) as total_alunos
                    FROM avaliacoes_habilidades av
                    WHERE av.fim_avaliacao >= CURRENT_DATE - INTERVAL '{self.DIAS_ANALISE} days'
                    GROUP BY EXTRACT(DOW FROM av.fim_avaliacao)
                """
                cursor.execute(query)
            
            padrao_historico = {i: 0 for i in range(0, 7)}
            for dia, total in cursor.fetchall():
                padrao_historico[int(dia)] = total
            
            total_historico = sum(padrao_historico.values())
            media_diaria = total_historico / self.DIAS_ANALISE if total_historico > 0 else 10
            
            dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            previsoes = []
            hoje = datetime.now()
            
            for i in range(7):
                data = hoje + timedelta(days=i)
                dia_num = data.weekday()
                
                fator_dia = padrao_historico.get(dia_num, media_diaria) / max(media_diaria, 1)
                previsto = media_diaria * fator_dia
                
                if fator_dia > 1.2:
                    classificacao = "PICO"
                    recomendacao = "Distribuir carga para dias mais calmos"
                elif fator_dia < 0.8:
                    classificacao = "VALE"
                    recomendacao = "Aproveitar para alocar mais avaliações"
                else:
                    classificacao = "NORMAL"
                    recomendacao = ""
                
                previsoes.append(PrevisaoDemanda(
                    dia_semana=dias_semana[dia_num],
                    data=data.strftime('%d/%m'),
                    previsao_avaliacoes=round(previsto, 0),
                    limite_superior=round(previsto * 1.3, 0),
                    limite_inferior=round(previsto * 0.7, 0),
                    classificacao=classificacao,
                    recomendacao=recomendacao
                ))
            
            return previsoes
        except Exception as e:
            print(f"Erro ao prever demanda: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    # ========== 5. MATRIZ DE DESEMPENHO (4 QUADRANTES) ==========
    
    def criar_matriz_desempenho_escolas(self, escolas_progresso: dict) -> List[MatrizQuadrante]:
        """Classifica escolas em 4 quadrantes baseado em eficiência e eficácia"""
        if not escolas_progresso:
            return []
        
        escolas_metrics = []
        for nome, dados in escolas_progresso.items():
            tempo_medio = dados.get('tempo_medio_minutos', 60)
            eficiencia = max(0, 100 - (tempo_medio / 60 * 100))
            
            alunos_avaliados = dados.get('alunos_avaliados', 0)
            alunos_totais = dados.get('alunos_totais', 1)
            eficacia = (alunos_avaliados / alunos_totais) * 100
            
            escolas_metrics.append({
                'nome': nome,
                'eficiencia': eficiencia,
                'eficacia': eficacia,
                'tempo_medio': tempo_medio
            })
        
        if not escolas_metrics:
            return []
        
        eficiencias = [e['eficiencia'] for e in escolas_metrics]
        eficacias = [e['eficacia'] for e in escolas_metrics]
        
        mediana_eficiencia = np.median(eficiencias)
        mediana_eficacia = np.median(eficacias)
        
        resultado = []
        
        for escola in escolas_metrics:
            if escola['eficiencia'] >= mediana_eficiencia and escola['eficacia'] >= mediana_eficacia:
                quadrante = "ESTRELA"
                cor = "#27AE60"
                acao = "Benchmark - Compartilhar práticas com outras escolas"
            elif escola['eficiencia'] >= mediana_eficiencia and escola['eficacia'] < mediana_eficacia:
                quadrante = "PRESSAO"
                cor = "#F39C12"
                acao = "Avaliar qualidade - Possível 'correria' comprometendo resultado"
            elif escola['eficiencia'] < mediana_eficiencia and escola['eficacia'] >= mediana_eficacia:
                quadrante = "POTENCIAL"
                cor = "#3498DB"
                acao = "Otimizar processos - Bom resultado, mas demorado"
            else:
                quadrante = "PROBLEMA"
                cor = "#E74C3C"
                acao = "INTERVENÇÃO URGENTE - Melhorar eficiência E eficácia"
            
            resultado.append(MatrizQuadrante(
                escola=escola['nome'],
                eficiencia=round(escola['eficiencia'], 1),
                eficacia=round(escola['eficacia'], 1),
                quadrante=quadrante,
                cor=cor,
                acao_recomendada=acao
            ))
        
        return resultado