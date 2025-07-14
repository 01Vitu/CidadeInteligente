import socket
import threading
import time
from generated import smart_city_pb2

# --- NOVA FUNÇÃO para detectar o IP local ---
def get_local_ip():
    """
    Descobre o endereço IP local da máquina na rede.
    Cria uma conexão UDP temporária para um destino externo para que o sistema
    operacional informe qual é o endereço IP da interface de rede preferencial.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Conecta-se a um servidor conhecido (não envia dados).
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        # Se falhar, usa o localhost como fallback.
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --- Configurações ---
# A variável GATEWAY_IP agora é preenchida dinamicamente.
GATEWAY_IP = get_local_ip()
DEVICE_TCP_PORT = 10000  # Porta para Dispositivos
CLIENT_TCP_PORT = 10003  # Nova porta para Clientes
UDP_PORT = 10001
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# --- Estado do Gateway ---
devices = {}
device_tcp_sockets = {}
lock = threading.Lock()

def discover_devices_periodically():
    """
    Anuncia a presença e as informações de conexão do Gateway na rede
    periodicamente via multicast.
    """
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(GATEWAY_IP))
    
    # --- MUDANÇA AQUI ---
    # Constrói uma mensagem estruturada com as informações de conexão do Gateway.
    wrapper_msg = smart_city_pb2.WrapperMessage()
    info = wrapper_msg.gateway_info
    info.ip_address = GATEWAY_IP
    info.device_tcp_port = DEVICE_TCP_PORT
    info.client_tcp_port = CLIENT_TCP_PORT
    
    # Serializa a mensagem para ser enviada.
    message = wrapper_msg.SerializeToString()
    
    while True:
        print(f"[DISCOVERY] Anunciando presença do Gateway ({GATEWAY_IP}) na rede...")
        multicast_socket.sendto(message, (MULTICAST_GROUP, MULTICAST_PORT))
        time.sleep(10)

# O restante do código permanece o mesmo, pois sua lógica já é robusta.
# As funções de manuseio de conexão e servidores TCP/UDP não precisam de alterações.

def handle_device_connection(conn):
    """Lida exclusivamente com a conexão de um dispositivo."""
    try:
        data = conn.recv(1024)
        if not data:
            conn.close()
            return

        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)

        if wrapper_msg.HasField("device_info"):
            info = wrapper_msg.device_info
            with lock:
                devices[info.id] = {'info': info, 'status': None}
                device_tcp_sockets[info.id] = conn
            device_type_name = smart_city_pb2.DeviceType.Name(info.type)
            print(f"--> SUCESSO: Dispositivo {info.id} ({device_type_name}) conectado.")
        else:
            print("[ERRO] Conexão na porta de dispositivos não se identificou.")
            conn.close()
    except Exception as e:
        print(f"[ERRO] Durante registro de dispositivo: {e}")
        conn.close()


def handle_client_connection(conn):
    """Lida exclusivamente com a conexão e os pedidos de um cliente."""
    print(f"[TCP-CLIENT] Cliente conectado de {conn.getpeername()}.")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break # Cliente desconectou

            wrapper_msg = smart_city_pb2.WrapperMessage()
            wrapper_msg.ParseFromString(data)
            
            if wrapper_msg.HasField("list_request"):
                print("[GATEWAY] Recebido pedido de listagem do cliente.")
                response_msg = smart_city_pb2.WrapperMessage()
                list_response = response_msg.list_response
                with lock:
                    for device_id, device_data in devices.items():
                        device_info = list_response.devices.add()
                        device_info.id = device_id
                        device_info.type = device_data['info'].type
                conn.send(response_msg.SerializeToString())
                print("[GATEWAY] Resposta da lista enviada.")

            elif wrapper_msg.HasField("command"):
                cmd = wrapper_msg.command
                print(f"[GATEWAY] Recebido comando para {cmd.device_id}.")
                target_socket = device_tcp_sockets.get(cmd.device_id)
                if target_socket:
                    target_socket.send(wrapper_msg.SerializeToString())
                else:
                    print(f"[ERRO] Dispositivo {cmd.device_id} não encontrado.")

    except Exception as e:
        print(f"Erro com cliente {conn.getpeername()}: {e}")
    finally:
        print(f"[TCP-CLIENT] Cliente {conn.getpeername()} desconectado.")
        conn.close()


def device_tcp_server():
    """Servidor TCP que escuta APENAS por dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, DEVICE_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-DEVICE] Gateway ouvindo por Dispositivos na porta {DEVICE_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_device_connection, args=(conn,), daemon=True).start()

def client_tcp_server():
    """Servidor TCP que escuta APENAS por clientes."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((GATEWAY_IP, CLIENT_TCP_PORT))
    server_socket.listen(5)
    print(f"[TCP-CLIENT] Gateway ouvindo por Clientes na porta {CLIENT_TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client_connection, args=(conn,), daemon=True).start()

def listen_for_udp_data():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # O bind é em "0.0.0.0" ou "" para aceitar pacotes de qualquer interface
    udp_socket.bind(("", UDP_PORT))
    print(f"[UDP] Gateway ouvindo por dados de sensores na porta {UDP_PORT}")
    while True:
        data, addr = udp_socket.recvfrom(1024)
        wrapper_msg = smart_city_pb2.WrapperMessage(); wrapper_msg.ParseFromString(data)
        if wrapper_msg.HasField("status_update"):
            status = wrapper_msg.status_update
            with lock:
                if status.device_id in devices:
                    devices[status.device_id]['status'] = status
                    if status.HasField("temperature"):
                        print(f"[UDP] Status recebido de {status.device_id}: Temperatura {status.temperature:.2f}°C")
                    elif status.HasField("state_info"):
                         print(f"[UDP] Status recebido de {status.device_id}: {status.state_info}")


if __name__ == "__main__":
    print(f"--- Gateway iniciando com IP dinâmico: {GATEWAY_IP} ---")
    
    threading.Thread(target=discover_devices_periodically, daemon=True).start()
    threading.Thread(target=listen_for_udp_data, daemon=True).start()
    threading.Thread(target=device_tcp_server, daemon=True).start()
    
    client_tcp_server()