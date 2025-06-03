import os
from flask import Flask, render_template_string, request, redirect, url_for, session, abort
import osmnx as ox
import networkx as nx
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from werkzeug.security import generate_password_hash, check_password_hash
import shapely.geometry

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Banco de dados de usuários fictício em memória
users_db = {
    "client1": {"password_hash": generate_password_hash("clientpass"), "role": "client", "active": True},
    "dev": {"password_hash": generate_password_hash("devpass"), "role": "dev", "active": True},
}

# Templates simples embutidos como strings
login_template = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; }
        .container { background-color: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }
        h1 { text-align: center; color: #333; }
        form div { margin-bottom: 1em; }
        label { display: block; margin-bottom: 0.5em; color: #555; }
        input[type="text"], input[type="password"] { width: calc(100% - 20px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        input[type="submit"] { background-color: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 1em; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .error { color: red; text-align: center; margin-bottom: 1em; }
        .links { text-align: center; margin-top: 1em; }
        .links a { color: #007bff; text-decoration: none; margin: 0 10px; }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ title }}</h1>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        <form method="post">
            <div>
                <label for="username">Usuário:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div>
                <label for="password">Senha:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div>
                <input type="submit" value="Entrar">
            </div>
        </form>
        <div class="links">
            <a href="{{ url_for('register') }}">Registrar como Cliente</a>
            {% if show_dev_link %}
                <a href="{{ url_for('dev_login') }}">Login Desenvolvedor</a>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

register_template = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registrar</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; }
        .container { background-color: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }
        h1 { text-align: center; color: #333; }
        form div { margin-bottom: 1em; }
        label { display: block; margin-bottom: 0.5em; color: #555; }
        input[type="text"], input[type="password"] { width: calc(100% - 20px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        input[type="submit"] { background-color: #28a745; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 1em; }
        input[type="submit"]:hover { background-color: #218838; }
        .error { color: red; text-align: center; margin-bottom: 1em; }
        .links { text-align: center; margin-top: 1em; }
        .links a { color: #007bff; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Registrar Conta de Cliente</h1>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        <form method="post">
            <div>
                <label for="username">Usuário:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div>
                <label for="password">Senha:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div>
                <input type="submit" value="Registrar">
            </div>
        </form>
        <div class="links">
            <a href="{{ url_for('login') }}">Voltar para Login</a>
        </div>
    </div>
</body>
</html>
"""

home_template = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Início - Planejador de Rotas para Veículos Pesados</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; }
        .container { background-color: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
        h1 { text-align: center; color: #333; }
        form div { margin-bottom: 1em; }
        label { display: block; margin-bottom: 0.5em; color: #555; }
        input[type="text"] { width: calc(100% - 20px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        input[type="submit"] { background-color: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 1em; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .logout-link { display: block; text-align: center; margin-top: 1.5em; }
        .logout-link a { color: #dc3545; text-decoration: none; }
        .logout-link a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Planejador de Rotas para Veículos Pesados</h1>
        <p>Bem-vindo(a), {{ session['username'] }}!</p>
        <form action="{{ url_for('route') }}" method="post">
            <div>
                <label for="origin">Origem:</label>
                <input type="text" id="origin" name="origin" placeholder="Ex: Belo Horizonte" required>
            </div>
            <div>
                <label for="destination">Destino:</label>
                <input type="text" id="destination" name="destination" placeholder="Ex: São Paulo" required>
            </div>
            <div>
                <input type="submit" value="Planejar Rota">
            </div>
        </form>
        <div class="logout-link">
            <a href="{{ url_for('logout') }}">Sair</a>
        </div>
    </div>
</body>
</html>
"""

route_template = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sua Rota</title>
    <style>
        body { font-family: sans-serif; margin: 0; display: flex; flex-direction: column; min-height: 100vh; }
        header { background-color: #333; color: white; padding: 1em; text-align: center; }
        .map-container { flex-grow: 1; display: flex; justify-content: center; align-items: center; }
        .map-frame { width: 100%; height: 80vh; border: none; }
        .back-link { text-align: center; padding: 1em; background-color: #f4f4f4; }
        .back-link a { color: #007bff; text-decoration: none; }
        .back-link a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <header>
        <h1>Sua Rota para Veículos Pesados</h1>
    </header>
    <div class="map-container">
        {{ folium_html | safe }}
    </div>
    <div class="back-link">
        <a href="{{ url_for('home') }}">Voltar para o Início</a>
    </div>
</body>
</html>
"""

dev_panel_template = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel do Desenvolvedor</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; }
        .container { background-color: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
        h1 { text-align: center; color: #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 1.5em; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        form { display: inline-block; margin-left: 10px; }
        button { padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; }
        .block-btn { background-color: #dc3545; color: white; }
        .block-btn:hover { background-color: #c82333; }
        .unblock-btn { background-color: #28a745; color: white; }
        .unblock-btn:hover { background-color: #218838; }
        .logout-link { text-align: center; margin-top: 2em; }
        .logout-link a { color: #dc3545; text-decoration: none; }
        .logout-link a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Painel do Desenvolvedor</h1>
        <h2>Gerenciar Clientes</h2>
        <table>
            <thead>
                <tr>
                    <th>Usuário</th>
                    <th>Função</th>
                    <th>Status</th>
                    <th>Ações</th>
                </tr>
            </thead>
            <tbody>
                {% for username, user_data in users.items() %}
                    {% if user_data.role == 'client' %}
                    <tr>
                        <td>{{ username }}</td>
                        <td>{{ user_data.role }}</td>
                        <td>{{ "Ativo" if user_data.active else "Bloqueado" }}</td>
                        <td>
                            <form action="{{ url_for('dev_block') }}" method="post">
                                <input type="hidden" name="username" value="{{ username }}">
                                {% if user_data.active %}
                                    <button type="submit" name="action" value="block" class="block-btn">Bloquear</button>
                                {% else %}
                                    <button type="submit" name="action" value="unblock" class="unblock-btn">Desbloquear</button>
                                {% endif %}
                            </form>
                        </td>
                    </tr>
                    {% endif %}
                {% endfor %}
            </tbody>
        </table>
        <div class="logout-link">
            <a href="{{ url_for('logout') }}">Sair</a>
        </div>
    </div>
</body>
</html>
"""


def is_logged_in():
    """Verifica se um usuário está logado."""
    return "username" in session and session["username"] in users_db


def current_user_role():
    """Retorna o papel do usuário logado, ou None se não estiver logado."""
    if not is_logged_in():
        return None
    return users_db[session["username"]]["role"]


def is_client_blocked(username):
    """Verifica se a conta de um cliente está bloqueada."""
    user = users_db.get(username)
    if not user:
        return True  # Trata usuários inexistentes como bloqueados por segurança
    return not user.get("active", False)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Lida com o login do cliente."""
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users_db.get(username)
        if user and check_password_hash(user["password_hash"], password) and user["role"] == "client":
            if user["active"]:
                session["username"] = username
                return redirect(url_for("home"))
            else:
                error = "Sua conta está bloqueada. Entre em contato com o desenvolvedor."
        else:
            error = "Usuário ou senha inválidos."
    return render_template_string(login_template, error=error, title="Login do Cliente", show_dev_link=True)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Lida com o registro de novos clientes."""
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users_db:
            error = "Nome de usuário já existe. Por favor, escolha outro."
        else:
            users_db[username] = {
                "password_hash": generate_password_hash(password),
                "role": "client",
                "active": True
            }
            return redirect(url_for("login"))
    return render_template_string(register_template, error=error)


@app.route("/dev_login", methods=["GET", "POST"])
def dev_login():
    """Lida com o login do desenvolvedor."""
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users_db.get(username)
        if user and check_password_hash(user["password_hash"], password) and user["role"] == "dev":
            session["username"] = username
            return redirect(url_for("dev_panel"))
        else:
            error = "Credenciais de desenvolvedor inválidas."
    return render_template_string(login_template, error=error, title="Login do Desenvolvedor", show_dev_link=False)


@app.route("/logout")
def logout():
    """Desloga o usuário atual."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    """Renderiza a página inicial para clientes."""
    if not is_logged_in():
        return redirect(url_for("login"))
    if current_user_role() != "client":
        abort(403)  # Proibido para não-clientes
    if is_client_blocked(session["username"]):
        return "Sua conta está bloqueada. Entre em contato com o desenvolvedor.", 403
    return render_template_string(home_template, session=session)


@app.route("/route", methods=["POST"])
def route():
    """Calcula e exibe a rota para veículos pesados."""
    if not is_logged_in() or current_user_role() != "client":
        return redirect(url_for("login"))
    if is_client_blocked(session["username"]):
        return "Sua conta está bloqueada. Entre em contato com o desenvolvedor.", 403

    origin = request.form.get("origin")
    destination = request.form.get("destination")
    if not origin or not destination:
        print("Erro: Origem e/ou destino não fornecidos.") # Log de erro
        return "Origem e destino são obrigatórios.", 400

    geolocator = Nominatim(user_agent="heavy_vehicle_route_planner")
    try:
        orig_loc = geolocator.geocode(origin)
        dest_loc = geolocator.geocode(destination)
        if not orig_loc or not dest_loc:
            print(f"Erro de Geocodificação: Não foi possível geocodificar '{origin}' ou '{destination}'.") # Log de erro
            return "Não foi possível geocodificar a origem ou o destino. Por favor, seja mais específico.", 400
    except Exception as e:
        print(f"Erro inesperado de Geocodificação: {e}") # Log de erro
        return f"Erro de geocodificação: {e}", 500

    # Obtém o grafo do OSM em torno de ambos os pontos com um buffer
    # Buffer aumentado ligeiramente para melhor cobertura do grafo
    north = max(orig_loc.latitude, dest_loc.latitude) + 0.05
    south = min(orig_loc.latitude, dest_loc.latitude) - 0.05
    east = max(orig_loc.longitude, dest_loc.longitude) + 0.05
    west = min(orig_loc.longitude, dest_loc.longitude) - 0.05

    # Cria a tupla da caixa delimitadora na ordem (oeste, sul, leste, norte)
    bbox = (west, south, east, north)

    try:
        print(f"Tentando baixar o grafo para bbox: {bbox}") # Log de status
        # Baixa o grafo da rede de estradas dirigíveis
        G = ox.graph_from_bbox(bbox, network_type='drive')
        print("Grafo baixado com sucesso.") # Log de status
    except Exception as e:
        print(f"Erro ao baixar o grafo do OSMnx: {e}") # Log de erro
        return f"Erro ao baixar o grafo do OSMnx: {e}. Por favor, tente novamente com outros locais.", 500

    def heavy_vehicle_filter(graph):
        """Filtra estradas inadequadas para veículos pesados."""
        g_filtered = graph.copy()
        to_remove = []
        for u, v, key, data in g_filtered.edges(keys=True, data=True):
            highway = data.get('highway')
            if isinstance(highway, list):
                highway = highway[0] # Pega o primeiro se for uma lista
            
            # Remove tipos de estrada inadequados
            unsuitable_highways = ['residential', 'service', 'footway', 'cycleway', 'path', 'steps', 'pedestrian', 'track', 'bridleway']
            if highway in unsuitable_highways:
                to_remove.append((u, v, key))
                continue
            
            # Verifica o atributo de largura se presente, evita estradas com menos de 4 metros aprox.
            width = data.get('width')
            if width:
                try:
                    # Converte a largura para float, assumindo que pode ser uma string (ex: "4.5")
                    wval = float(width)
                    if wval < 4.0:
                        to_remove.append((u, v, key))
                except ValueError:
                    # Ignora se a largura não for um número válido
                    pass
        
        # Remove arestas ruins
        g_filtered.remove_edges_from(to_remove)
        # Remove nós isolados que podem resultar da remoção de arestas
        g_filtered.remove_nodes_from(list(nx.isolates(g_filtered)))
        return g_filtered

    print("Aplicando filtro de veículos pesados ao grafo...") # Log de status
    G_filtered = heavy_vehicle_filter(G)
    print(f"Grafo filtrado. Número de nós: {len(G_filtered.nodes)}, Número de arestas: {len(G_filtered.edges)}") # Log de status


    # Obtém os nós mais próximos dos pontos de origem e destino no grafo filtrado
    try:
        print(f"Procurando nós mais próximos para origem ({orig_loc.longitude}, {orig_loc.latitude}) e destino ({dest_loc.longitude}, {dest_loc.latitude})...") # Log de status
        orig_node = ox.distance.nearest_nodes(G_filtered, orig_loc.longitude, orig_loc.latitude)
        dest_node = ox.distance.nearest_nodes(G_filtered, dest_loc.longitude, dest_loc.latitude)
        print(f"Nós encontrados: Origem={orig_node}, Destino={dest_node}") # Log de status
    except Exception as e:
        print(f"Erro ao encontrar nós próximos: {e}") # Log de erro
        return f"Não foi possível encontrar nós próximos na rede de estradas filtrada: {e}. Tente locais diferentes ou amplie a área de busca.", 500

    try:
        print("Calculando o caminho mais curto...") # Log de status
        route_nodes = nx.shortest_path(G_filtered, orig_node, dest_node, weight='length')
        print("Caminho mais curto calculado com sucesso.") # Log de status
    except nx.NetworkXNoPath:
        print("Erro: Nenhuma rota encontrada (NetworkXNoPath).") # Log de erro
        return "Nenhuma rota para veículos pesados encontrada entre os locais especificados. As estradas podem ser inadequadas ou muito distantes.", 400
    except Exception as e:
        print(f"Erro inesperado ao calcular a rota: {e}") # Log de erro
        return f"Erro ao calcular a rota: {e}", 500

    # Obtém os pontos de latitude e longitude da rota
    route_points = [(G_filtered.nodes[n]['y'], G_filtered.nodes[n]['x']) for n in route_nodes]

    # Encontra pontos de interesse (postos de gasolina, restaurantes) dentro do buffer da rota
    pois = None
    try:
        print("Buscando pontos de interesse (POIs)...") # Log de status
        line = shapely.geometry.LineString([(lon, lat) for lat, lon in route_points])
        buffer = line.buffer(0.005)  # buffer em graus, ajuste conforme necessário
        tags = {'amenity': ['fuel', 'restaurant']}
        # Garante que o buffer é válido para consultas de geometria
        if not buffer.is_empty:
            pois = ox.geometries.geometries_from_polygon(buffer, tags)
            print(f"POIs encontrados: {len(pois) if pois is not None else 0}") # Log de status
    except Exception as e:
        print(f"Erro ao buscar POIs: {e}") # Log o erro, mas não interrompe a execução

    # Cria o mapa folium centrado no ponto médio da rota
    mid_lat = (orig_loc.latitude + dest_loc.latitude) / 2
    mid_lon = (orig_loc.longitude + dest_loc.longitude) / 2
    fmap = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles='CartoDB positron')

    # Adiciona a polilinha da rota
    folium.PolyLine(route_points, color='blue', weight=6, opacity=0.7, tooltip="Rota para veículos pesados").add_to(fmap)

    # Adiciona marcadores de origem e destino
    folium.Marker([orig_loc.latitude, orig_loc.longitude], popup=f"Origem: {origin}", icon=folium.Icon(color='green', icon='play')).add_to(fmap)
    folium.Marker([dest_loc.latitude, dest_loc.longitude], popup=f"Destino: {destination}", icon=folium.Icon(color='red', icon='stop')).add_to(fmap)

    # Adiciona marcadores de POI com agrupamento
    if pois is not None and not pois.empty:
        cluster = MarkerCluster(name="POI").add_to(fmap)
        for idx, poi in pois.iterrows():
            if poi.geometry.is_empty:
                continue
            
            # Lida com diferentes tipos de geometria para POIs
            lat, lon = None, None
            if poi.geometry.geom_type == 'Point':
                lat, lon = poi.geometry.y, poi.geometry.x
            elif poi.geometry.geom_type in ['Polygon', 'MultiPolygon']:
                lat, lon = poi.geometry.centroid.y, poi.geometry.centroid.x
            
            if lat is not None and lon is not None:
                name = poi.get('name', 'N/A')
                amenity = poi.get('amenity', '')
                popup_text = f"{amenity.title()}: {name}"
                icon_color = 'orange' if amenity == 'fuel' else 'cadetblue' if amenity == 'restaurant' else 'gray'
                folium.Marker([lat, lon], popup=popup_text, icon=folium.Icon(color=icon_color, icon='info-sign')).add_to(cluster)
    
    folium.LayerControl().add_to(fmap) # Adiciona controle de camada para o cluster de POIs

    # Renderiza os componentes do mapa Folium em HTML
    fmap_html = fmap.get_root().render()

    print("Mapa Folium gerado e pronto para renderização.") # Log de status
    return render_template_string(route_template, folium_html=fmap_html)


@app.route("/dev_panel", methods=["GET"])
def dev_panel():
    """Renderiza o painel do desenvolvedor para gerenciar contas de clientes."""
    if not is_logged_in() or current_user_role() != "dev":
        return redirect(url_for("dev_login"))
    return render_template_string(dev_panel_template, users=users_db)


@app.route("/dev_block", methods=["POST"])
def dev_block():
    """Lida com o bloqueio/desbloqueio de contas de clientes por desenvolvedores."""
    if not is_logged_in() or current_user_role() != "dev":
        return redirect(url_for("dev_login"))
    username = request.form.get("username")
    action = request.form.get("action")
    if username in users_db and users_db[username]["role"] == "client":
        if action == "block":
            users_db[username]["active"] = False
        elif action == "unblock":
            users_db[username]["active"] = True
    return redirect(url_for("dev_panel"))


if __name__ == "__main__":
    print("Iniciando o aplicativo Planejador de Rotas para Veículos Pesados em http://127.0.0.1:5000")
    app.run(debug=True)