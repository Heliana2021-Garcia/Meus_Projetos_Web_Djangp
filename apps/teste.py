@property
def motivos_inelegibilidade(self):
    motivos = []                                              # 1
    if self.registo_estado != self.Registo.APROVADO:          # 2
        motivos.append("O seu registo ainda não foi validado pela coordenação.")   # 3
    if self.ano_frequencia < self.ANO_MINIMO_CANDIDATURA:     # 4
        motivos.append("É necessário frequentar o 3º ano ou superior.")            # 5
    if self.media_geral < self.MEDIA_MINIMA_CANDIDATURA:      # 6
        motivos.append("A média geral tem de ser pelo menos 14.00 valores.")       # 7
    return motivos                                            # 8