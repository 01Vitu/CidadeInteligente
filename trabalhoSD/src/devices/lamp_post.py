# src/devices/lamp_post.py
import socket
import threading
import time
import uuid
from generated import smart_city_pb2

# --- Configurações ---
DEVICE_ID = f"lamp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('LAMP_POST')
# As configurações do Gateway (IP, Porta TCP) foram removidas pois serão descobertas automaticamente.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Dispositivo ---
is_on = False

# A função listen_for_commands permanece a mesma, pois sua lógica interna não muda.
def listen_for_commands(tcp_socket):
    global is_on
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
                if cmd.device_id == DEVICE_ID and cmd.HasField("toggle"):
                    is_on = not is_on
                    print(f"--> Comando recebido! Poste de Luz ({DEVICE_ID}) agora está {'LIGADO' if is_on else 'DESLIGADO'}.")
    except ConnectionResetError:
        print("Conexão com o Gateway foi resetada.")
    except Exception as e:
        print(f"Erro ao receber comando: {e}")
    finally:
        tcp_socket.close()

# --- NOVA FUNÇÃO DE DESCOBERTA E CONEXÃO ---
def discover_gateway_and_connect():
    """
    Escuta por anúncios do Gateway via multicast para descobrir seu IP e porta,
    e então estabelece uma conexão TCP para se registrar.
    """
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Poste de Luz ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
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
                
                # Envia a mensagem de registro do dispositivo.
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                
                print(f"--> SUCESSO: Registrado no Gateway. Aguardando comandos.")
                
                # Inicia a thread para escutar por comandos.
                command_thread = threading.Thread(target=listen_for_commands, args=(tcp_socket,), daemon=True)
                command_thread.start()
                break

            except Exception as e:
                print(f"Falha ao conectar no Gateway descoberto: {e}")
                time.sleep(5) # Aguarda antes de tentar novamente

if __name__ == "__main__":
    discover_gateway_and_connect()
    # Mantém o processo principal vivo para a thread de comandos.
    while True:
        time.sleep(3600)