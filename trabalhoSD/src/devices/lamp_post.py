# src/devices/lamp_post.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
# Define as constantes do dispositivo, como seu ID único, tipo, e os endereços de rede do Gateway.
DEVICE_ID = f"lamp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('LAMP_POST')
GATEWAY_IP = "192.168.1.7"
GATEWAY_TCP_PORT = 10000
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
# Variável global que armazena o estado atual do poste (ligado ou desligado).
is_on = False

def listen_for_commands(tcp_socket):
    """
    Escuta por comandos do Gateway na conexão TCP persistente.
    
    Esta função roda em uma thread e fica bloqueada esperando dados do Gateway.
    Ao receber um comando, ela o processa e altera o estado do dispositivo.
    """
    global is_on
    try:
        while True:
            # Aguarda o recebimento de dados do Gateway.
            data = tcp_socket.recv(1024)
            if not data:
                print("Conexão com o Gateway perdida.")
                break
            
            # Decodifica a mensagem recebida.
            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            # Verifica se é um comando e se é para este dispositivo.
            if wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                if cmd.device_id == DEVICE_ID and cmd.HasField("toggle"):
                    # Inverte o estado atual (liga se estiver desligado, e vice-versa).
                    is_on = not is_on
                    print(f"--> Comando recebido! Poste de Luz ({DEVICE_ID}) agora está {'LIGADO' if is_on else 'DESLIGADO'}.")
    except ConnectionResetError:
        print("Conexão com o Gateway foi resetada.")
    except Exception as e:
        print(f"Erro ao receber comando: {e}")
    finally:
        tcp_socket.close()

def listen_for_discovery():
    """
    Aguarda o sinal de descoberta (multicast) do Gateway para iniciar a conexão.
    """
    # Configura o socket para receber mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Poste de Luz ({DEVICE_ID}) aguardando descoberta...")
    while True:
        # Fica bloqueado até receber uma mensagem de descoberta.
        data, address = multicast_socket.recvfrom(1024)
        if data == b"GATEWAY_DISCOVERY":
            print("--> Descoberta recebida do Gateway! Tentando conectar via TCP...")
            # Inicia o processo de conexão TCP após a descoberta.
            connect_to_gateway()
            break # Encerra o loop de descoberta.

def connect_to_gateway():
    """Conecta-se ao Gateway via TCP para se registrar e começar a ouvir por comandos."""
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_socket.connect((GATEWAY_IP, GATEWAY_TCP_PORT))
        
        # Envia uma mensagem de registro com seu ID e tipo.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        info = wrapper_msg.device_info
        info.id = DEVICE_ID
        info.type = DEVICE_TYPE
        tcp_socket.send(wrapper_msg.SerializeToString())
        print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
        
        # Inicia uma thread separada para escutar por comandos, mantendo a conexão aberta.
        command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
        command_thread.start()
    except Exception as e:
        print(f"Falha ao conectar/registrar no Gateway: {e}")
        if tcp_socket:
            tcp_socket.close()

# Bloco principal que inicia o processo de descoberta.
if __name__ == "__main__":
    listen_for_discovery()
    # Mantém o processo principal vivo para que a thread de comandos possa continuar rodando.
    while True:
        time.sleep(3600)
