# src/devices/traffic_light.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"sema_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('TRAFFIC_LIGHT')
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
is_on = False
red_light_duration = 15

# A função listen_for_commands permanece a mesma.
def listen_for_commands(tcp_socket):
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
                    if cmd.HasField("toggle"):
                        is_on = not is_on
                        print(f"--> Comando 'toggle' recebido! Semáforo agora está {'LIGADO' if is_on else 'DESLIGADO'}.")
                    if cmd.HasField("new_config"):
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

# --- NOVA FUNÇÃO DE DESCOBERTA E CONEXÃO ---
def discover_gateway_and_connect():
    """Escuta e conecta ao Gateway descoberto automaticamente."""
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Semáforo ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    while True:
        data, address = multicast_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            discovered_port = gateway_info.device_tcp_port
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Conectando...")
            
            try:
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                
                print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
                
                command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
                command_thread.start()
                break
            except Exception as e:
                print(f"Falha ao conectar no Gateway descoberto: {e}")
                time.sleep(5)

if __name__ == "__main__":
    discover_gateway_and_connect()
    while True:
        time.sleep(3600)