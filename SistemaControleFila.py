import os
from flask import Flask, render_template_string, request, redirect, url_for, session, abort
import osmnx as ox
import networkx as nx
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Dummy in-memory user database
# Format: username: {password_hash: ..., role: "client"/"dev", active: True/False}
users_db = {
    "client1": {"password_hash": generate_password_hash("clientpass"), "role": "client", "active": True},
    "dev": {"password_hash": generate_password_hash("devpass"), "role": "dev", "active": True},
}

# Simple templates inline as strings for the demo

login_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Login</title>
  <style>
    body { font-family: Arial, sans-serif; background: #2c3e50; color: #ecf0f1; }
    .container { max-width: 400px; margin: 100px auto; background: #34495e; padding: 20px; border-radius: 8px; }
    input[type=text], input[type=password] {
      width: 100%; padding: 10px; margin: 8px 0; border: none; border-radius: 4px;
    }
    button {
      background-color: #27ae60; border: none; color: white; padding: 10px; width: 100%; border-radius: 4px;
      font-size: 16px; cursor: pointer;
    }
    button:hover { background-color: #2ecc71; }
    h2 { text-align: center; }
    a {color:#ecf0f1;}
  </style>
</head>
<body>
  <div class="container">
    <h2>{{ title }}</h2>
    {% if error %}<p style="color:#e74c3c;">{{ error }}</p>{% endif %}
    <form method="POST">
      <label>Username</label>
      <input type="text" name="username" required />
      <label>Password</label>
      <input type="password" name="password" required />
      <button type="submit">Login</button>
    </form>
    {% if show_dev_link %}
    <p><a href="{{ url_for('dev_login') }}">Developer Login</a></p>
    {% else %}
    <p><a href="{{ url_for('login') }}">Client Login</a></p>
    {% endif %}
  </div>
</body>
</html>
"""

home_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Heavy Vehicle Route Planner</title>
  <style>
    body { font-family: Arial, sans-serif; background: #34495e; color: #ecf0f1; margin:0; padding:0; }
    header { background: #2c3e50; padding: 15px; text-align: center; font-size: 24px; }
    main { padding: 20px; max-width: 600px; margin: 0 auto; }
    input[type=text] {
      width: 100%; padding: 10px; margin: 8px 0; border: none; border-radius: 4px;
      font-size: 16px;
    }
    button {
      background-color: #27ae60; border: none; color: white; padding: 12px; width: 100%; border-radius: 4px;
      font-size: 18px; cursor: pointer;
    }
    button:hover { background-color: #2ecc71; }
    .logout { margin-top: 10px; color: #ecf0f1; text-align: center; }
    .logout a {color:#e74c3c; text-decoration:none;}
    .logout a:hover {text-decoration: underline;}
  </style>
</head>
<body>
  <header>Heavy Vehicle Route Planner</header>
  <main>
    <form method="POST" action="{{ url_for('route') }}">
      <label for="origin">Origin address:</label><br />
      <input type="text" id="origin" name="origin" placeholder="Enter starting location" required /><br />
      <label for="destination">Destination address:</label><br />
      <input type="text" id="destination" name="destination" placeholder="Enter destination location" required /><br />
      <button type="submit">Calculate Route</button>
    </form>
    <div class="logout">
      Logged in as {{ session['username'] }} | <a href="{{ url_for('logout') }}">Logout</a>
    </div>
  </main>
</body>
</html>
"""

route_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Route Result</title>
  <style>
    body { margin: 0; padding: 0; font-family: Arial, sans-serif; background: #2c3e50; color: #ecf0f1; }
    #map { height: 90vh; width: 100%; }
    header { background: #34495e; padding: 15px; text-align: center; font-size: 24px; }
    .back { padding: 10px; text-align: center; }
    .back a {
      background-color: #27ae60; color: white; padding: 10px 20px; border-radius: 5px;
      text-decoration: none; font-size: 16px;
    }
    .back a:hover { background-color: #2ecc71; }
  </style>
  {{ folium_map | safe }}
</head>
<body>
  <header>Route Result</header>
  <div id="map"></div>
  <div class="back"><a href="{{ url_for('home') }}">New Route</a></div>

  <script>
    // Folium script to mount map in #map
    document.getElementById('map').innerHTML = `{{ folium_html | safe }}`;
  </script>
</body>
</html>
"""

dev_panel_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Developer Panel</title>
  <style>
    body { font-family: Arial, sans-serif; background: #2c3e50; color: #ecf0f1; }
    .container { max-width: 600px; margin: 50px auto; padding: 20px; background: #34495e; border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px; border: 1px solid #7f8c8d; text-align: center; }
    th { background-color: #27ae60; }
    form { display: inline; }
    button { background-color: #e74c3c; border: none; color: white; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
    button:hover { background-color: #c0392b; }
    h2 { margin-bottom: 20px; }
    a {color:#ecf0f1; display:block; margin-top:20px; text-align:center; text-decoration:none;}
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <h2>Developer Panel - User Management</h2>
    <table>
      <tr><th>Username</th><th>Role</th><th>Active</th><th>Action</th></tr>
      {% for user, data in users.items() %}
      <tr>
        <td>{{ user }}</td>
        <td>{{ data.role }}</td>
        <td>{{ 'Yes' if data.active else 'No' }}</td>
        <td>
          {% if data.role == 'client' %}
          <form method="POST" action="{{ url_for('dev_block') }}">
            <input type="hidden" name="username" value="{{ user }}" />
            {% if data.active %}
            <button name="action" value="block" type="submit">Block</button>
            {% else %}
            <button name="action" value="unblock" type="submit">Unblock</button>
            {% endif %}
          </form>
          {% else %}
            N/A
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </table>
    <a href="{{ url_for('logout') }}">Logout</a>
  </div>
</body>
</html>
"""

def is_logged_in():
    return "username" in session and session["username"] in users_db

def current_user_role():
    if not is_logged_in():
        return None
    return users_db[session["username"]]["role"]

def is_client_blocked(username):
    user = users_db.get(username)
    if not user:
        return True
    return not user.get("active", False)

@app.route("/login", methods=["GET", "POST"])
def login():
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
                error = "Your account is blocked. Contact developer."
        else:
            error = "Invalid username or password."
    return render_template_string(login_template, error=error, title="Client Login", show_dev_link=True)

@app.route("/dev_login", methods=["GET", "POST"])
def dev_login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users_db.get(username)
        if user and check_password_hash(user["password_hash"], password) and user["role"] == "dev":
            session["username"] = username
            return redirect(url_for("dev_panel"))
        else:
            error = "Invalid developer credentials."
    return render_template_string(login_template, error=error, title="Developer Login", show_dev_link=False)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if not is_logged_in():
        return redirect(url_for("login"))
    if current_user_role() != "client":
        abort(403)
    if is_client_blocked(session["username"]):
        return "Your account is blocked. Contact developer.", 403
    return render_template_string(home_template)

@app.route("/route", methods=["POST"])
def route():
    if not is_logged_in() or current_user_role() != "client":
        return redirect(url_for("login"))
    if is_client_blocked(session["username"]):
        return "Your account is blocked. Contact developer.", 403

    origin = request.form.get("origin")
    destination = request.form.get("destination")
    if not origin or not destination:
        return "Origin and destination required", 400

    geolocator = Nominatim(user_agent="heavy_vehicle_app")
    try:
        orig_loc = geolocator.geocode(origin)
        dest_loc = geolocator.geocode(destination)
        if not orig_loc or not dest_loc:
            return "Could not geocode origin or destination.", 400
    except Exception as e:
        return f"Geocoding error: {e}", 500

    # Get graph from OSM around both points with a buffer
    north = max(orig_loc.latitude, dest_loc.latitude) + 0.02
    south = min(orig_loc.latitude, dest_loc.latitude) - 0.02
    east = max(orig_loc.longitude, dest_loc.longitude) + 0.02
    west = min(orig_loc.longitude, dest_loc.longitude) - 0.02

    try:
        # Download drivable road network graph
        G = ox.graph_from_bbox(north, south, east, west, network_type='drive')
    except Exception as e:
        return f"OSMnx graph download error: {e}", 500

    # Filter edges to avoid narrow streets for heavy vehicles
    # We'll remove edges with highway type 'residential', 'service', or narrow ways if width data available
    def heavy_vehicle_filter(G):
        to_remove = []
        for u,v,key,data in G.edges(keys=True, data=True):
            highway = data.get('highway')
            if isinstance(highway, list):
                highway = highway[0]
            # Remove unsuitable highway types
            if highway in ['residential', 'service', 'footway', 'cycleway', 'path', 'steps', 'pedestrian']:
                to_remove.append((u,v,key))
                continue
            # Check width attribute if present, avoid roads less than 4 meters approx.
            width = data.get('width')
            if width:
                try:
                    wval = float(width)
                    if wval < 4.0:
                        to_remove.append((u,v,key))
                except:
                    pass
        # Remove bad edges
        G.remove_edges_from(to_remove)
        # Remove isolated nodes
        G.remove_nodes_from(list(nx.isolates(G)))
        return G

    G = heavy_vehicle_filter(G)

    # Get nearest nodes to origin and destination points
    orig_node = ox.distance.nearest_nodes(G, orig_loc.longitude, orig_loc.latitude)
    dest_node = ox.distance.nearest_nodes(G, dest_loc.longitude, dest_loc.latitude)

    try:
        route_nodes = nx.shortest_path(G, orig_node, dest_node, weight='length')
    except Exception as e:
        return f"No route found: {e}", 500

    # Get route latitude and longitude points
    route_points = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route_nodes]

    # Find points of interest (gas stations, restaurants) within buffer of the route
    try:
        # Create a polygon around route with buffering (approx 0.005 degrees ~500m)
        import shapely.geometry
        line = shapely.geometry.LineString([(lon, lat) for lat, lon in route_points])
        buffer = line.buffer(0.005)  # buffer in degrees
        tags = {'amenity': ['fuel', 'restaurant']}
        pois = ox.geometries.geometries_from_polygon(buffer, tags)
    except Exception as e:
        pois = None

    # Create folium map centered at midpoint of route
    mid_lat = (orig_loc.latitude + dest_loc.latitude) / 2
    mid_lon = (orig_loc.longitude + dest_loc.longitude) / 2
    fmap = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles='CartoDB positron')

    # Add route polyline
    folium.PolyLine(route_points, color='blue', weight=6, opacity=0.7, tooltip="Heavy vehicle route").add_to(fmap)

    # Add origin and destination markers
    folium.Marker([orig_loc.latitude, orig_loc.longitude], popup="Origin", icon=folium.Icon(color='green', icon='play')).add_to(fmap)
    folium.Marker([dest_loc.latitude, dest_loc.longitude], popup="Destination", icon=folium.Icon(color='red', icon='stop')).add_to(fmap)

    # Add POI markers with clustering
    if pois is not None and not pois.empty:
        cluster = MarkerCluster(name="POI").add_to(fmap)
        for idx, poi in pois.iterrows():
            if poi.geometry.is_empty:
                continue
            if poi.geometry.geom_type == 'Point':
                lat, lon = poi.geometry.y, poi.geometry.x
            elif poi.geometry.geom_type in ['Polygon', 'MultiPolygon']:
                lat, lon = poi.geometry.centroid.y, poi.geometry.centroid.x
            else:
                continue
            name = poi.get('name', 'POI')
            amenity = poi.get('amenity', '')
            popup_text = f"{amenity.title()}: {name}"
            icon_color = 'orange' if amenity == 'fuel' else 'cadetblue' if amenity == 'restaurant' else 'gray'
            folium.Marker([lat, lon], popup=popup_text, icon=folium.Icon(color=icon_color, icon='info-sign')).add_to(cluster)

    # Render Folium HTML map components
    fmap_html = fmap.get_root().render()

    return render_template_string(route_template, folium_map='', folium_html=fmap_html)

@app.route("/dev_panel", methods=["GET"])
def dev_panel():
    if not is_logged_in() or current_user_role() != "dev":
        return redirect(url_for("dev_login"))
    return render_template_string(dev_panel_template, users=users_db)

@app.route("/dev_block", methods=["POST"])
def dev_block():
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
    # To run: python app.py
    # Requirements: flask, osmnx, networkx, folium, geopy, shapely, werkzeug
    # Install them using: pip install flask osmnx networkx folium geopy shapely werkzeug
    print("Starting Heavy Vehicle Route Planner app on http://127.0.0.1:5000")
    app.run(debug=True)

