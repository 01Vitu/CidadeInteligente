# src/devices/air_sensor.py
import socket
import threading
import time
import uuid
import random
from generated import smart_city_pb2

# --- Configurações ---
# Constantes de rede, incluindo a porta UDP para envio de status.
DEVICE_ID = f"airq_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('AIR_SENSOR')
GATEWAY_IP = "192.168.1.7"
GATEWAY_TCP_PORT = 10000
GATEWAY_UDP_PORT = 10001 # Porta específica para dados UDP.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

def send_status_updates(udp_socket):
    """
    Envia periodicamente dados de qualidade do ar via UDP.
    
    Esta função roda em uma thread e, a cada 15 segundos, gera um valor
    aleatório de qualidade do ar e o envia para o Gateway via UDP.
    """
    while True:
        # Simula uma leitura de Partículas Por Milhão (PPM).
        air_quality_ppm = round(random.uniform(30.0, 150.0), 2)
        
        # Monta a mensagem de status.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        status = wrapper_msg.status_update
        status.device_id = DEVICE_ID
        status.state_info = f"PPM: {air_quality_ppm}"
        
        # Envia os dados para o Gateway usando o socket UDP.
        udp_socket.sendto(wrapper_msg.SerializeToString(), (GATEWAY_IP, GATEWAY_UDP_PORT))
        print(f"Enviado status: Qualidade do Ar = {air_quality_ppm:.2f} PPM")
        time.sleep(15)

def listen_for_discovery():
    """Aguarda o sinal de descoberta do Gateway para se registrar."""
    # Configura o socket para receber mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Sensor de Qualidade do Ar ({DEVICE_ID}) aguardando descoberta...")
    
    while True:
        data, address = multicast_socket.recvfrom(1024)
        if data == b"GATEWAY_DISCOVERY":
            print("--> Descoberta recebida. Registrando e iniciando envio de dados.")
            try:
                # Conexão TCP rápida usada APENAS para o registro inicial.
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((GATEWAY_IP, GATEWAY_TCP_PORT))
                
                # Envia as informações de identificação.
                wrapper_msg = smart_city_pb2.WrapperMessage()
                info = wrapper_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                
                tcp_socket.send(wrapper_msg.SerializeToString())
                print("--> SUCESSO: Registrado no Gateway.")
                tcp_socket.close() # Fecha a conexão TCP imediatamente após o registro.
                
                # Inicia a thread que enviará os dados via UDP.
                update_thread = threading.Thread(target=send_status_updates, args=(socket.socket(socket.AF_INET, socket.SOCK_DGRAM),), daemon=True)
                update_thread.start()
                break
            except Exception as e:
                print(f"Falha ao registrar via TCP: {e}")
            
if __name__ == "__main__":
    listen_for_discovery()
    # Mantém o processo principal vivo para a thread de envio de status.
    while True:
        time.sleep(3600)
