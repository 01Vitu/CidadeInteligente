# src/devices/camera.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"cam_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('CAMERA')
GATEWAY_IP = "192.168.1.7"
GATEWAY_TCP_PORT = 10000
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
is_on = False
resolution = "HD" # Estado inicial

def listen_for_commands(tcp_socket):
    """Escuta por comandos do Gateway na conexão TCP persistente."""
    global is_on, resolution
    try:
        while True:
            data = tcp_socket.recv(1024)
            if not data:
                print("Conexão com o Gateway perdida.")
                break
                
            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            if wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                if cmd.device_id == DEVICE_ID:
                    # Lidar com comando 'toggle'
                    if cmd.HasField("toggle"):
                        is_on = not is_on
                        print(f"--> Comando 'toggle' recebido! Câmera agora está {'LIGADA' if is_on else 'DESLIGADA'}.")
                    
                    # Lidar com comando 'new_config'
                    if cmd.HasField("new_config"):
                        # Exemplo de formato esperado: "resolution:FullHD"
                        try:
                            key, value = cmd.new_config.split(':')
                            if key.lower() == "resolution":
                                resolution = value
                                print(f"--> Comando 'config' recebido! Resolução alterada para {resolution}.")
                            else:
                                print(f"Configuração desconhecida: {key}")
                        except ValueError:
                            print(f"Formato de configuração inválido recebido: {cmd.new_config}")

    except ConnectionResetError:
        print("Conexão com o Gateway foi resetada.")
    except Exception as e:
        print(f"Erro ao receber comando: {e}")
    finally:
        tcp_socket.close()

def listen_for_discovery():
    """Aguarda o sinal de descoberta do Gateway."""
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Câmera ({DEVICE_ID}) aguardando descoberta...")
    
    while True:
        data, address = multicast_socket.recvfrom(1024)
        if data == b"GATEWAY_DISCOVERY":
            print("--> Descoberta recebida! Conectando ao Gateway...")
            connect_to_gateway()
            break

def connect_to_gateway():
    """Conecta-se ao Gateway via TCP para se registrar e receber comandos."""
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_socket.connect((GATEWAY_IP, GATEWAY_TCP_PORT))
        
        wrapper_msg = smart_city_pb2.WrapperMessage()
        info = wrapper_msg.device_info
        info.id = DEVICE_ID
        info.type = DEVICE_TYPE
        
        tcp_socket.send(wrapper_msg.SerializeToString())
        print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
        
        # Inicia a thread para escutar comandos na conexão estabelecida
        command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
        command_thread.start()
    except Exception as e:
        print(f"Falha ao conectar/registrar no Gateway: {e}")
        if tcp_socket:
            tcp_socket.close()

if __name__ == "__main__":
    listen_for_discovery()
    # Mantém o processo principal vivo para a thread de comandos continuar rodando
    while True:
        time.sleep(3600)