import tkinter as tk
from tkinter import ttk
import pandas as pd
import geopandas as gpd
import folium
import unidecode
import webbrowser
import os

# Caminhos para os arquivos
data_path = "C:/Dev/projeto_universidade/data/"
shapefile_path = "C:/Dev/projeto_universidade/shapefiles/SP_Mesorregioes_2022.shp"
output_path = "C:/Dev/projeto_universidade/output/"

# Função para padronizar os nomes das cidades
def padronizar_nome(cidade):
    cidade = unidecode.unidecode(cidade).lower()
    cidade = (cidade.replace("'", "")
                     .replace(" ", "")
                     .replace("-", "")
                     .replace("/", "")
                     .replace("(", "")
                     .replace(")", "")
                     .replace("ç", "c")
                     .replace("ã", "a")
                     .replace("õ", "o")
                     .replace("á", "a")
                     .replace("é", "e")
                     .replace("í", "i")
                     .replace("ó", "o")
                     .replace("ú", "u")
                     .replace("â", "a")
                     .replace("ê", "e")
                     .replace("î", "i")
                     .replace("ô", "o")
                     .replace("û", "u")
                     .replace("ä", "a")
                     .replace("ë", "e")
                     .replace("ï", "i")
                     .replace("ö", "o")
                     .replace("ü", "u")
                     .replace("à", "a")
                     .replace("è", "e")
                     .replace("ì", "i")
                     .replace("ò", "o")
                     .replace("ù", "u"))
    return cidade

# Carregando arquivos CSV
mesorregioes_df = pd.read_csv(data_path + "MESORREGIOES_SP.csv", encoding='latin1', delimiter=';')
mesorregioes_df['cidade'] = mesorregioes_df['cidade'].apply(padronizar_nome)

universidade_df = pd.read_csv(data_path + "UNIVERSIDADE_SP.csv", encoding='latin1', delimiter=';')
universidade_df['Município'] = universidade_df['Município'].apply(padronizar_nome)

idh_df = pd.read_csv(data_path + "IDH.csv", delimiter=";", quotechar='"', encoding='latin1')
idh_df.columns = idh_df.columns.str.strip()
idh_df['Localidades'] = idh_df['Localidades'].apply(padronizar_nome)

emprego_formal_df = pd.read_csv(data_path + "EMPREGO_FORMAL.csv", delimiter=";", quotechar='"', encoding='latin1')
emprego_formal_df.columns = emprego_formal_df.columns.str.strip()
emprego_formal_df['Localidades'] = emprego_formal_df['Localidades'].apply(padronizar_nome)

renda_per_capita_df = pd.read_csv(data_path + "RENDA_PER_CAPITA.csv", delimiter=";", quotechar='"', encoding='latin1')
renda_per_capita_df.columns = renda_per_capita_df.columns.str.strip()
renda_per_capita_df['Localidades'] = renda_per_capita_df['Localidades'].apply(padronizar_nome)

cursos_df = pd.read_csv(data_path + "CURSOS_SP.csv", delimiter=";", quotechar='"', encoding='latin1')
cursos_df.columns = cursos_df.columns.str.strip()

# Carregando o arquivo COORDENADAS.csv com codificação UTF-8-SIG para corrigir caracteres
coordenadas_df = pd.read_csv(data_path + "COORDENADAS.csv", encoding='utf-8-sig', delimiter=';')
coordenadas_df = coordenadas_df[coordenadas_df['uf'] == 'SP']
coordenadas_df['municipio'] = coordenadas_df['municipio'].apply(padronizar_nome)

# Carregando o shapefile das mesorregiões para uso no mapa
mesorregioes_gdf = gpd.read_file(shapefile_path)

# Contando o número de faculdades por município e ordenando em ordem decrescente
faculdades_por_cidade = universidade_df.groupby('Município')['Código IES'].nunique().sort_values(ascending=False)

# **Adição: Impressão das Cidades com Mais Universidades no CMD**
print("\n=== Cidades com Mais Universidades em São Paulo ===\n")
for cidade, count in faculdades_por_cidade.items():
    print(f"{cidade.capitalize()}: {count} universidade(s)")
print("\n===============================================\n")
# **Fim da Adição**

# Função para calcular a pontuação de uma cidade com normalização e proporção
def calcular_pontuacao(cidade, idh_df, emprego_formal_df, renda_per_capita_df, peso_idh, peso_emprego, peso_renda):
    # Obtendo o valor do IDH
    idh_valor = idh_df.loc[idh_df['Localidades'] == cidade, 'Índice de Desenvolvimento Humano Municipal - IDHM']
    idh_score = float(idh_valor.values[0].replace(",", ".")) if not idh_valor.empty else 0.0

    # Calculando a proporção de empregos formais ocupados por pessoas com ensino superior
    emprego_total = emprego_formal_df.loc[emprego_formal_df['Localidades'] == cidade, 'Empregos Formais']
    emprego_superior = emprego_formal_df.loc[emprego_formal_df['Localidades'] == cidade, 'Empregos Formais das Pessoas com Ensino Superior Completo']
    
    emprego_score = (float(emprego_superior.values[0]) / float(emprego_total.values[0])) if (not emprego_total.empty and not emprego_superior.empty and emprego_total.values[0] > 0) else 0.0

    # Normalizando a renda per capita em relação ao valor máximo da lista
    renda_valor = renda_per_capita_df.loc[renda_per_capita_df['Localidades'] == cidade, 'Renda per Capita - Censo Demográfico (Em reais correntes)']
    renda_maxima = renda_per_capita_df['Renda per Capita - Censo Demográfico (Em reais correntes)'].max()
    renda_score = (float(renda_valor.values[0].replace(",", ".")) / float(renda_maxima.replace(",", "."))) if not renda_valor.empty else 0.0

    # Cálculo da pontuação total
    pontuacao_total = (peso_idh * idh_score) + (peso_emprego * emprego_score) + (peso_renda * renda_score)

    # Exibindo as pontuações individuais para verificação
    print(f"IDH Score: {idh_score}, Emprego Score: {emprego_score}, Renda Score: {renda_score}")

    return pontuacao_total


# Função para gerar o mapa com seleção dos 10 cursos mais populares da mesorregião para a cidade escolhida
def gerar_mapa(peso_idh, peso_emprego, peso_renda, proximidade_concorrencia):
    # Dicionário para armazenar a melhor cidade para cada mesorregião
    melhores_cidades = {}

    # Associar `cursos_df` com `universidade_df` usando `Código IES` para incluir o município em cada curso
    cursos_universidades_df = cursos_df.merge(
        universidade_df[['Código IES', 'Município']],
        left_on='Código IES',
        right_on='Código IES',
        how='left'
    )

    # Garantir que todos os valores em 'Município' são strings, tratando NaNs
    cursos_universidades_df['Município'] = cursos_universidades_df['Município'].fillna('').astype(str)
    
    # Aplicar a função padronizar_nome na coluna 'Município'
    cursos_universidades_df['Município'] = cursos_universidades_df['Município'].apply(padronizar_nome)

    # Associar cursos com suas respectivas mesorregiões por meio do município
    cursos_mesorregioes_df = cursos_universidades_df.merge(
        mesorregioes_df[['cidade', 'mesorregiao']],
        left_on='Município',
        right_on='cidade',
        how='left'
    )

    # Iterar por cada mesorregião e identificar a melhor cidade e cursos recomendados
    for mesorregiao in mesorregioes_df["mesorregiao"].unique():
        cidades_na_mesorregiao = mesorregioes_df[mesorregioes_df["mesorregiao"] == mesorregiao]["cidade"]

        # Lista para armazenar cidades e suas pontuações
        cidades_pontuacoes = []

        for cidade in cidades_na_mesorregiao:
            pontuacao = calcular_pontuacao(cidade, idh_df, emprego_formal_df, renda_per_capita_df, peso_idh, peso_emprego, peso_renda)
            cidades_pontuacoes.append((cidade, pontuacao))
        
        # Ordenar as cidades pela pontuação descendente
        cidades_pontuacoes.sort(key=lambda x: x[1], reverse=True)

        melhor_cidade = None
        maior_pontuacao = -1

        if proximidade_concorrencia == "Próximo":
            # Selecionar a cidade com a maior pontuação
            if cidades_pontuacoes:
                melhor_cidade, maior_pontuacao = cidades_pontuacoes[0]
        elif proximidade_concorrencia == "Distante":
            # Tentar encontrar a primeira cidade que tenha ≥4 faculdades
            for cidade, pontuacao in cidades_pontuacoes:
                num_faculdades = faculdades_por_cidade.get(cidade, 0)
                if num_faculdades >= 4:
                    melhor_cidade = cidade
                    maior_pontuacao = pontuacao
                    break

            # Se nenhuma cidade com ≥4 faculdades atender ao critério, selecionar a cidade com maior pontuação (primeira da lista)
            if not melhor_cidade and cidades_pontuacoes:
                melhor_cidade, maior_pontuacao = cidades_pontuacoes[0]

        # Recomendação dos 10 cursos mais populares da mesorregião para a cidade selecionada
        if melhor_cidade:
            # Filtra os cursos da mesorregião e seleciona os 10 mais populares
            cursos_mesorregiao = cursos_mesorregioes_df[cursos_mesorregioes_df['mesorregiao'] == mesorregiao]
            cursos_mais_populares = (cursos_mesorregiao['Nome do Curso']
                                     .value_counts()
                                     .head(10)
                                     .index.tolist())
            
            # Armazenando a cidade e os cursos recomendados para exibição
            melhores_cidades[mesorregiao] = {
                "cidade": melhor_cidade,
                "pontuacao": maior_pontuacao,
                "cursos": cursos_mais_populares
            }


    # Exibindo resultados no console
    print("\nResumo das melhores cidades e cursos recomendados por mesorregião:\n")
    for mesorregiao, info in melhores_cidades.items():
        print(f"Mesorregião: {mesorregiao}")
        print(f"Melhor Cidade: {info['cidade'].capitalize()} com pontuação: {info['pontuacao']:.2f}")
        print("Cursos Recomendados:")
        for curso in info['cursos']:
            print(f"  - {curso}")
        print("\n" + "-"*50 + "\n")

    # Salvar mapa HTML (opcional)
    mapa = folium.Map(location=[-23.55052, -46.6333], zoom_start=7)
    for _, row in mesorregioes_gdf.iterrows():
        sim_geo = gpd.GeoSeries(row['geometry']).simplify(tolerance=0.001)
        geo_j = sim_geo.to_json()
        folium.GeoJson(geo_j, name=row['NM_MESO']).add_to(mapa)

    # Adicionando marcadores no mapa
    for mesorregiao, info in melhores_cidades.items():
        cidade = info["cidade"]
        coordenada = coordenadas_df[coordenadas_df['municipio'] == cidade][['latitude', 'longitude']]
        if not coordenada.empty:
            lat, lon = coordenada.iloc[0]
        else:
            print(f"Aviso: Coordenadas não encontradas para a cidade '{cidade}'. Usando coordenadas padrão.")
            lat, lon = -23.55052, -46.6333  # Coordenadas padrão

        cursos_info = "<br>".join(info['cursos'])
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>Mesorregião:</b> {mesorregiao}<br><b>Cidade:</b> {cidade.capitalize()}<br><b>Pontuação:</b> {info['pontuacao']:.2f}<br><b>Cursos:</b><br>{cursos_info}",
            tooltip=cidade.capitalize()
        ).add_to(mapa)

    mapa_file = os.path.join(output_path, "mapa_recomendado.html")
    mapa.save(mapa_file)
    print(f"Mapa com recomendações gerado em '{mapa_file}'")

    # Abrir o mapa automaticamente no navegador padrão
    webbrowser.open('file://' + os.path.realpath(mapa_file))

# Função para capturar as configurações do usuário e iniciar o cálculo
def iniciar_calculo():
    # Obtém valores dos pesos a partir dos sliders
    peso_idh = idh_scale.get()
    peso_emprego = emprego_scale.get()
    peso_renda = renda_scale.get()

    # Define proximidade com concorrência
    proximidade_concorrencia = var_concorrencia.get()

    print("Configurações atuais:")
    print(f"Peso IDH: {peso_idh}")
    print(f"Peso Emprego: {peso_emprego}")
    print(f"Peso Renda: {peso_renda}")
    print(f"Proximidade com a concorrência: {proximidade_concorrencia}")

    gerar_mapa(peso_idh, peso_emprego, peso_renda, proximidade_concorrencia)

# Configuração da janela inicial
root = tk.Tk()
root.title("Configurações Iniciais")

# Campo para o peso do IDH usando Scale (slider)
tk.Label(root, text="Peso IDH:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
idh_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
idh_scale.set(0.4)  # Valor padrão
idh_scale.grid(row=0, column=1, padx=5, pady=5)

# Campo para o peso de Emprego usando Scale (slider)
tk.Label(root, text="Peso Emprego:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
emprego_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
emprego_scale.set(0.3)  # Valor padrão
emprego_scale.grid(row=1, column=1, padx=5, pady=5)

# Campo para o peso de Renda usando Scale (slider)
tk.Label(root, text="Peso Renda:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
renda_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
renda_scale.set(0.3)  # Valor padrão
renda_scale.grid(row=2, column=1, padx=5, pady=5)

# Opção para proximidade com concorrência
var_concorrencia = tk.StringVar(value="Próximo")
tk.Label(root, text="Deseja ficar próximo ou distante da concorrência?").grid(row=3, column=0, columnspan=2, padx=5, pady=5)
ttk.Radiobutton(root, text="Próximo", variable=var_concorrencia, value="Próximo").grid(row=4, column=0, padx=5, pady=5, sticky='w')
ttk.Radiobutton(root, text="Distante", variable=var_concorrencia, value="Distante").grid(row=4, column=1, padx=5, pady=5, sticky='w')

# Botão para iniciar o cálculo e gerar o mapa
tk.Button(root, text="Gerar Mapa", command=iniciar_calculo).grid(row=5, column=0, columnspan=2, padx=10, pady=20)

# Executa a interface
root.mainloop()
