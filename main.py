import tkinter as tk
from tkinter import ttk
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster, MiniMap, MeasureControl
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

# Carregando arquivos CSV e shapefile
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

coordenadas_df = pd.read_csv(data_path + "COORDENADAS.csv", encoding='utf-8-sig', delimiter=';')
coordenadas_df = coordenadas_df[coordenadas_df['uf'] == 'SP']
coordenadas_df['municipio'] = coordenadas_df['municipio'].apply(padronizar_nome)

mesorregioes_gdf = gpd.read_file(shapefile_path)
faculdades_por_cidade = universidade_df.groupby('Município')['Código IES'].nunique().sort_values(ascending=False)

# Função para calcular a pontuação de uma cidade com normalização e proporção
def calcular_pontuacao(cidade, idh_df, emprego_formal_df, renda_per_capita_df, peso_idh, peso_emprego, peso_renda):
    idh_valor = idh_df.loc[idh_df['Localidades'] == cidade, 'Índice de Desenvolvimento Humano Municipal - IDHM']
    idh_score = float(idh_valor.values[0].replace(",", ".")) if not idh_valor.empty else 0.0

    emprego_total = emprego_formal_df.loc[emprego_formal_df['Localidades'] == cidade, 'Empregos Formais']
    emprego_superior = emprego_formal_df.loc[emprego_formal_df['Localidades'] == cidade, 'Empregos Formais das Pessoas com Ensino Superior Completo']
    
    emprego_score = (float(emprego_superior.values[0]) / float(emprego_total.values[0])) if (not emprego_total.empty and not emprego_superior.empty and emprego_total.values[0] > 0) else 0.0

    renda_valor = renda_per_capita_df.loc[renda_per_capita_df['Localidades'] == cidade, 'Renda per Capita - Censo Demográfico (Em reais correntes)']
    renda_maxima = renda_per_capita_df['Renda per Capita - Censo Demográfico (Em reais correntes)'].max()
    renda_score = (float(renda_valor.values[0].replace(",", ".")) / float(renda_maxima.replace(",", "."))) if not renda_valor.empty else 0.0

    pontuacao_total = (peso_idh * idh_score) + (peso_emprego * emprego_score) + (peso_renda * renda_score)

    return pontuacao_total

# Função para gerar o mapa
def gerar_mapa(peso_idh, peso_emprego, peso_renda, proximidade_concorrencia):
    melhores_cidades = {}
    cursos_universidades_df = cursos_df.merge(
        universidade_df[['Código IES', 'Município']],
        left_on='Código IES',
        right_on='Código IES',
        how='left'
    )

    cursos_universidades_df['Município'] = cursos_universidades_df['Município'].fillna('').astype(str)
    cursos_universidades_df['Município'] = cursos_universidades_df['Município'].apply(padronizar_nome)

    cursos_mesorregioes_df = cursos_universidades_df.merge(
        mesorregioes_df[['cidade', 'mesorregiao']],
        left_on='Município',
        right_on='cidade',
        how='left'
    )

    for mesorregiao in mesorregioes_df["mesorregiao"].unique():
        cidades_na_mesorregiao = mesorregioes_df[mesorregioes_df["mesorregiao"] == mesorregiao]["cidade"]
        cidades_pontuacoes = []

        for cidade in cidades_na_mesorregiao:
            pontuacao = calcular_pontuacao(cidade, idh_df, emprego_formal_df, renda_per_capita_df, peso_idh, peso_emprego, peso_renda)
            cidades_pontuacoes.append((cidade, pontuacao))
        
        cidades_pontuacoes.sort(key=lambda x: x[1], reverse=True)

        melhor_cidade = None
        maior_pontuacao = -1

        if proximidade_concorrencia == "Próximo":
            if cidades_pontuacoes:
                melhor_cidade, maior_pontuacao = cidades_pontuacoes[0]
        elif proximidade_concorrencia == "Distante":
            # Ordena as cidades com base na menor quantidade de faculdades, priorizando menor concorrência
            cidades_pontuacoes = sorted(cidades_pontuacoes, key=lambda x: faculdades_por_cidade.get(x[0], 0))
    
            # Seleciona a cidade com menor concorrência (menos faculdades)
            if cidades_pontuacoes:
                melhor_cidade, maior_pontuacao = cidades_pontuacoes[0]

        if melhor_cidade:
            cursos_mesorregiao = cursos_mesorregioes_df[cursos_mesorregioes_df['mesorregiao'] == mesorregiao]
            cursos_mais_populares = (cursos_mesorregiao['Nome do Curso']
                                     .value_counts()
                                     .head(10)
                                     .index.tolist())
            
            melhores_cidades[mesorregiao] = {
                "cidade": melhor_cidade,
                "pontuacao": maior_pontuacao,
                "cursos": cursos_mais_populares
            }

    # Configuração do mapa com minimapa, controle de medida e clusters
    mapa = folium.Map(location=[-23.55052, -46.6333], zoom_start=7)
    minimap = MiniMap(toggle_display=True)
    mapa.add_child(minimap)
    measure_control = MeasureControl(primary_length_unit='kilometers')
    mapa.add_child(measure_control)
    marker_cluster = MarkerCluster().add_to(mapa)
    
    # Camada GeoJson com legendas e estilos personalizados
    for _, row in mesorregioes_gdf.iterrows():
        sim_geo = gpd.GeoSeries(row['geometry']).simplify(tolerance=0.001)
        geo_j = sim_geo.to_json()
        folium.GeoJson(
            geo_j,
            name=row['NM_MESO'],
            style_function=lambda x: {'fillColor': '#3186cc', 'color': 'black', 'weight': 1, 'fillOpacity': 0.5},
            highlight_function=lambda x: {'fillColor': '#ffaf00', 'color': 'black', 'weight': 2, 'fillOpacity': 0.7},
            tooltip=f"Mesorregião: {row['NM_MESO']}"
        ).add_to(mapa)

    # Adicionando marcadores com pop-ups detalhados
    for mesorregiao, info in melhores_cidades.items():
        cidade = info["cidade"]
        coordenada = coordenadas_df[coordenadas_df['municipio'] == cidade][['latitude', 'longitude']]
        if not coordenada.empty:
            lat, lon = coordenada.iloc[0]
        else:
            lat, lon = -23.55052, -46.6333

        cursos_info = "<br>".join(info['cursos'])
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>Mesorregião:</b> {mesorregiao}<br><b>Cidade:</b> {cidade.capitalize()}<br><b>Pontuação:</b> {info['pontuacao']:.2f}<br><b>Cursos:</b><br>{cursos_info}",
            tooltip=cidade.capitalize()
        ).add_to(marker_cluster)

    # Adicionando uma legenda no canto inferior direito do mapa
    legend_html = '''
     <div style="position: fixed; 
                 bottom: 50px; left: 50px; width: 250px; height: 140px; 
                 background-color: white; opacity: 0.8; z-index:9999; font-size:14px;
                 border:2px solid grey; border-radius:8px;">
     <div style="text-align:center; font-weight: bold">Legenda</div>
     <ul style="list-style:none; padding-left: 10px;">
       <li><span style="background-color:#3186cc; width: 15px; height: 15px; display:inline-block; margin-right: 5px;"></span> Mesorregiões</li>
       <li><span style="background-color:#ffaf00; width: 15px; height: 15px; display:inline-block; margin-right: 5px;"></span> Destaque ao passar o mouse</li>
       <li><span style="color:green;">•</span> Cidade com recomendação</li>
     </ul>
     </div>
     '''
    mapa.get_root().html.add_child(folium.Element(legend_html))

    mapa_file = os.path.join(output_path, "mapa_recomendado.html")
    mapa.save(mapa_file)
    webbrowser.open('file://' + os.path.realpath(mapa_file))

# Função para capturar as configurações do usuário e iniciar o cálculo
def iniciar_calculo():
    peso_idh = idh_scale.get()
    peso_emprego = emprego_scale.get()
    peso_renda = renda_scale.get()
    proximidade_concorrencia = var_concorrencia.get()

    gerar_mapa(peso_idh, peso_emprego, peso_renda, proximidade_concorrencia)

# Configuração da janela inicial
root = tk.Tk()
root.title("Configurações Iniciais")

# Campo para o peso do IDH usando Scale (slider)
tk.Label(root, text="Peso | IDH:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
idh_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
idh_scale.set(0.3)  # Valor padrão
idh_scale.grid(row=0, column=1, padx=5, pady=5)

# Campo para o peso de Emprego usando Scale (slider)
tk.Label(root, text="Peso | Empregos Ensino Superior:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
emprego_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
emprego_scale.set(0.3)  # Valor padrão
emprego_scale.grid(row=1, column=1, padx=5, pady=5)

# Campo para o peso de Renda usando Scale (slider)
tk.Label(root, text="Peso | Renda:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
renda_scale = tk.Scale(root, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL)
renda_scale.set(0.3)  # Valor padrão
renda_scale.grid(row=2, column=1, padx=5, pady=5)

# Opção para proximidade com concorrência
var_concorrencia = tk.StringVar(value="Próximo")
tk.Label(root, text="Deseja ficar próximo ou distante da concorrência?").grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky='w')
ttk.Radiobutton(root, text="Próximo", variable=var_concorrencia, value="Próximo").grid(row=4, column=0, padx=5, pady=5, sticky='w')
ttk.Radiobutton(root, text="Distante", variable=var_concorrencia, value="Distante").grid(row=4, column=1, padx=5, pady=5, sticky='w')

# Botão para iniciar o cálculo e gerar o mapa
tk.Button(root, text="Gerar Mapa", command=iniciar_calculo).grid(row=5, column=0, columnspan=2, padx=10, pady=20)

# Executa a interface
root.mainloop()
