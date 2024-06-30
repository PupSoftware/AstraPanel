import docker, re, os, uuid, pty, os, subprocess, select, termios, struct, fcntl
from dataclasses import dataclass
from flask_socketio import SocketIO
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, redirect, url_for, request, session, copy_current_request_context
app = Flask(__name__)

from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

app.config["SECRET_KEY"] = "0xEssjBdpVDww8yoOhrrArNVIXsTx2QL13mA4AuhIawiCFvGpqSRk5fOFCcsoeXyB6"

app.config["DISCORD_CLIENT_ID"]     = os.environ["DISCORD_CLIENT_ID"]
app.config["DISCORD_CLIENT_SECRET"] = os.environ["DISCORD_CLIENT_SECRET"]
app.config["DISCORD_REDIRECT_URI"]  = os.environ["DISCORD_REDIRECT_URI"]
TMATE_API_KEY                       = os.environ["TMATE_API_KEY"]
SERVER_LIMIT                        = int(os.environ["SERVER_LIMIT"])
SITE_TITLE                          = os.environ["SITE_TITLE"]
database_file                       = os.environ["database_file"]
VM_IMAGES                           = os.environ["VM_IMAGES"].split(",")


discord = DiscordOAuth2Session(app)
socketio = SocketIO(app, ping_interval=10, async_handlers=False)

@dataclass
class Server:
    id: int
    container_name: str
    ssh_session_line: str
    status: int
    def __eq__(self, other):
        return (self.container_name == other.container_name)
    
@dataclass
class MsgColors:
    success=0
    error=1
    warning=2

def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

@app.route("/xterm")
@requires_authorization
def index():
    return render_template("terminal.html", SITE_TITLE=SITE_TITLE, CONTAINER_ID=request.args.get("containerid", ""))

@socketio.on("pty-input", namespace="/pty")
@requires_authorization
def pty_input(data):
    container_id = make_safe(request.args.get("containerid"))
    if session[f"fd-{container_id}"]:
        os.write(session[f"fd-{container_id}"], data["input"].encode())

@socketio.on("resize", namespace="/pty")
@requires_authorization
def resize(data):
    container_id = make_safe(request.args.get("containerid"))
    if session[f"fd-{container_id}"]:
        set_winsize(session[f"fd-{container_id}"], data["rows"], data["cols"])

def make_safe(cid):
    cid = cid.replace(" ", "")
    cid = "".join(list(filter(lambda s: (str.isalnum(s) or s == "_"), cid)))
    user = discord.fetch_user()
    servers = get_user_servers(user.username)
    if not Server(0, cid, "", 0) in servers:
        cid = "\033[0;31m this_is_not_your_server \033[0m"
    return cid

def custom_regex(str):
    regex = [" - - ","["," ",":",":","]"," ", "/socket.io/?containerid=", "&", "HTTP/1.1"]
    last_index = 0
    removed_lenght = 0
    for part in regex:
        if part in str:
            tmp_i = str.index(part)
            if (removed_lenght + tmp_i) > last_index:
                last_index = tmp_i
                str = str[tmp_i + len(part):]
                removed_lenght += tmp_i + len(part)
            else:
                return False
        else:
            return False
    return True

@socketio.on("connect", namespace="/pty")
@requires_authorization
def connect(*args, **kwargs):
    container_id = make_safe(request.args.get("containerid"))
    if session.get(f"proccess-{container_id}", False):
        return

    session[f"fd-{container_id}"] = session[f"exited-{container_id}"] = session[f"child_pid-{container_id}"] = None
    (child_pid, fd) = pty.fork()
    if child_pid == 0:
        "”"
        tmp_args = request.args.get("cmd_args",[])
        if not tmp_args == []:
            tmp_args = tmp_args.split(" ")
            subprocess.run(tmp_args)
        "”"
        subprocess.run(["docker", "exec", "-it", container_id, "/bin/bash"])
        return "this is astravm vpsmanager terminal close exit code"
    else:
        session[f"fd-{container_id}"] = fd
        session[f"child_pid-{container_id}"] = child_pid
        set_winsize(fd, 50, 50)
        
        @copy_current_request_context
        def read_and_forward_pty_output(container_id):
            max_read_bytes = 1024 * 20
            while True:
                socketio.sleep(0.01)
                if session[f"fd-{container_id}"] and session[f"child_pid-{container_id}"]:
                    timeout_sec = 0
                    (data_ready, _, _) = select.select([session[f"fd-{container_id}"]], [], [], timeout_sec)
                    if data_ready:
                        try:
                            if not session[f"exited-{container_id}"]:
                                output = os.read(session[f"fd-{container_id}"], max_read_bytes).decode(
                                    errors="ignore"
                                )
                                if "this is astravm vpsmanager terminal close exit code" in output or "ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2426)" in output or custom_regex(output):
                                    socketio.emit("pty-output", {"output": "\n\n\n \033[0;31m Disconnected \033[0m", "close_con": True}, namespace="/pty")
                                else:
                                    socketio.emit("pty-output", {"output": output}, namespace="/pty")
                        except:
                            pass
                            # socketio.emit("pty-output", {"output": "\033[0;31m Unable to create connection to the machine \033[0m", "close_con": True}, namespace="/pty")
                            # socketio.server.disconnect(socketio)
        
        socketio.start_background_task(target=lambda: read_and_forward_pty_output(container_id))
        

@app.route("/callback")
def callback():
    discord.callback()
    return redirect(url_for("home"))

@app.route("/login")
def login():
    return discord.create_session()

@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

try:
    client = docker.from_env()
except docker.errors.DockerException as e:
    print(f"Error connecting to Docker: {e}")
    exit(1)

def get_user_servers(user):
    servers = []
    count = 0
    if not os.path.exists(database_file):
        return servers
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                l = line.split("|")
                tmp = client.containers.get(l[1])
                servers.append(Server(id=count, container_name=l[1], ssh_session_line=l[2], status=(1 if tmp.status == "running" else 0)))
                count += 1
    return servers

def get_user_server_id(user):
    servers = []
    if not os.path.exists(database_file):
        return servers
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.split("|")[1])
    return servers

def count_user_servers(user):
    count = 0
    if not os.path.exists(database_file):
        return count
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                count += 1
    return count
    
def add_to_database(user, container_name, ssh_session_line):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_session_line}\n")
        
def remove_from_database(user, container_name):
    with open(database_file, "r") as f:
        data = f.read()
        for line in data.split("\n"):
            if line.startswith(f"{user}|{container_name}|"):
                data = data.replace(line, "")
        with open(database_file, "w") as f2:
            f2.write(data)
        
def check_id(id):
    user = discord.fetch_user()
    return (id in get_user_server_id(user.username))

@app.route("/")
def base():
    return redirect(url_for("home"))

@app.route("/home")
@requires_authorization
def home():
    user = discord.fetch_user()
    servers = get_user_servers(user.username)
    return render_template("homePage.html", site_title=SITE_TITLE, servers=servers, user=user, servers_count=len(servers))
    
@app.route("/create_new")
@requires_authorization
def create_new():
    user = discord.fetch_user()
    return render_template("newPage.html", site_title=SITE_TITLE, user=user, images=VM_IMAGES)


@app.route("/api/restart", methods=["POST"])
@requires_authorization
def restart():
    try:
        data = request.get_json()["id"]
        if not check_id(data): return {"success": False, "error": "Error! :|"}
        tmp = client.containers.get(data)
        tmp.restart(timeout=5)
        return {"success": True}
    except:
        return {"success": False, "error": "Error! :|"}
    
@app.route("/api/delete", methods=["POST"])
@requires_authorization
def delete():
    try:
        user = discord.fetch_user()
        data = request.get_json()["id"]
        if not check_id(data): return {"success": False, "error": "Error! :|"}
        tmp = client.containers.get(data)
        tmp.remove(v=True, force=True)
        remove_from_database(user.username, data)
        return {"success": True}
    except:
        return {"success": False, "error": "Error! :|"}
    
@app.route("/api/stop", methods=["POST"])
@requires_authorization
def stop():
    try:
        data = request.get_json()["id"]
        if not check_id(data): return {"success": False, "error": "Error! :|"}
        tmp = client.containers.get(data)
        tmp.stop(timeout=5)
        return {"success": True}
    except:
        return {"success": False, "error": "Error! :|"}
    
@app.route("/api/start", methods=["POST"])
@requires_authorization
def start():
    try:
        data = request.get_json()["id"]
        if not check_id(data): return {"success": False, "error": "Error! :|"}
        tmp = client.containers.get(data)
        tmp.start()
        return {"success": True}
    except:
        return {"success": False, "error": "Error! :|"}

def get_ssh_session_line(container):
    def get_ssh_session(logs):
        match = re.search(r'ssh session: (ssh [^\n]+)', logs)
        if match and "ro-" not in match.group(1):
            return match.group(1)
        return None

    ssh_session_line = None
    max_attempts = 300000
    attempt = 0

    while attempt < max_attempts:
        logs = container.logs().decode('utf-8')
        ssh_session_line = get_ssh_session(logs)
        if ssh_session_line:
            break
        attempt += 1

    return ssh_session_line

def creationlog(msg):
    socketio.sleep(0.01)
    socketio.emit("creation_log", {"output":msg}, namespace="/server_creation")

def creationerror(data):
    socketio.sleep(0.01)
    socketio.emit("creation_log", {"error":data}, namespace="/server_creation")

@socketio.on("connect", namespace="/server_creation")
def create_server_task():
    image = request.args.get("image")
    if not image in VM_IMAGES:
        creationerror({"message": f"Error: {image} is not in available images: {VM_IMAGES}", "message_color": MsgColors.warning})
        return
    user = discord.fetch_user()
    if count_user_servers(user.username) >= SERVER_LIMIT:
        creationerror({"message": "Error: Server Limit-reached\n\nLogs:\nFailed to run apt update\nFailed to run apt install tmate\nFailed to run tmate -F\nError: Server Limit-reached", "message_color": MsgColors.warning})
        return

    commands = f"""
    apt update && \
    apt install -y tmate && \
    tmate -k {TMATE_API_KEY} -n {uuid.uuid4()} -F
    """

    creationlog(f"Creating container using {image} ...")

    try:
        container = client.containers.run(image, command="sh -c '{}'".format(commands), detach=True, tty=True)
    except Exception as e:
        creationerror({"message":f"Error creating container: {e}", "message_color": MsgColors.error})

    creationlog("Container created ✅")

    creationlog("Checking machine's health ...")

    ssh_session_line = get_ssh_session_line(container)
    if ssh_session_line:
        add_to_database(user.username, container.name, ssh_session_line)
        creationlog("Successfully created VPS")
        socketio.emit("creation_log", {"redirect": url_for("home")}, namespace="/server_creation")
    else:
        container.stop()
        container.remove()
        creationerror({"message":"Something went wrong or the server is taking longer than expected. if this problem continues, Contact Support.", "message_color":MsgColors.error})

if __name__ == "__main__":
    app.run(ssl_context=(os.environ["SSL_CERTIFICATE_FILE"], os.environ["SSL_KEY_FILE"]), debug=True)