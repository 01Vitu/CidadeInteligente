# src/devices/traffic_light.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"sema_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('TRAFFIC_LIGHT')
GATEWAY_IP = "192.168.1.7"
GATEWAY_TCP_PORT = 10000
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
is_on = False
red_light_duration = 15 # Duração em segundos

def listen_for_commands(tcp_socket):
    """Escuta por comandos do Gateway na conexão TCP persistente."""
    global is_on, red_light_duration
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
                        print(f"--> Comando 'toggle' recebido! Semáforo agora está {'LIGADO' if is_on else 'DESLIGADO'}.")
                    
                    # Lidar com comando 'new_config'
                    if cmd.HasField("new_config"):
                        # Exemplo de formato esperado: "duration:20"
                        try:
                            key, value = cmd.new_config.split(':')
                            if key.lower() == "duration":
                                new_duration = int(value)
                                red_light_duration = new_duration
                                print(f"--> Comando 'config' recebido! Duração do sinal vermelho alterada para {red_light_duration}s.")
                            else:
                                print(f"Configuração desconhecida: {key}")
                        except (ValueError, TypeError):
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
    
    print(f"Semáforo ({DEVICE_ID}) aguardando descoberta...")
    
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
        
        command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
        command_thread.start()
    except Exception as e:
        print(f"Falha ao conectar/registrar no Gateway: {e}")
        if tcp_socket:
            tcp_socket.close()

if __name__ == "__main__":
    listen_for_discovery()
    while True:
        time.sleep(3600)