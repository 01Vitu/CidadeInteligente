# src/devices/temp_sensor.py
import socket
import threading
import time
import uuid
import random
from generated import smart_city_pb2

# --- Configurações ---
# Define um ID e tipo únicos para este dispositivo.
DEVICE_ID = f"temp_{uuid.uuid4().hex[:6]}"
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('TEMP_SENSOR')
# A porta UDP do Gateway para onde os status serão enviados. Mantida como constante por simplicidade.
GATEWAY_UDP_PORT = 10001
# Constantes para a comunicação multicast de descoberta.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

def send_status_updates(udp_socket, gateway_ip):
    """
    Envia periodicamente dados de temperatura via UDP para o Gateway.

    Esta função roda em uma thread e, a cada 15 segundos, gera um valor
    aleatório de temperatura e o envia para o IP do Gateway que foi
    descoberto dinamicamente.
    """
    while True:
        # Simula uma leitura de temperatura em graus Celsius.
        temp = round(random.uniform(22.0, 31.0), 2)
        
        # Constrói a mensagem de status usando o campo específico 'temperature'.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        status = wrapper_msg.status_update
        status.device_id = DEVICE_ID
        status.temperature = temp
        
        # Envia os dados para o Gateway via UDP. UDP é "sem conexão",
        # então o endereço de destino é especificado a cada envio.
        udp_socket.sendto(wrapper_msg.SerializeToString(), (gateway_ip, GATEWAY_UDP_PORT))
        print(f"Enviado status: Temperatura = {temp:.2f}°C para {gateway_ip}")
        # Pausa de 15 segundos.
        time.sleep(15)

def discover_gateway_and_connect():
    """
    Escuta por anúncios do Gateway na rede para se registrar e, em seguida,
    inicia o envio periódico de status via UDP.
    """
    # Configura o socket para escutar por mensagens multicast.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Sensor de Temperatura ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    # Loop de descoberta.
    while True:
        # Fica bloqueado aqui até receber um anúncio multicast.
        data, address = multicast_socket.recvfrom(1024)
        
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        # Verifica se a mensagem é um anúncio do Gateway.
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            discovered_port = gateway_info.device_tcp_port
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Registrando...")

            try:
                # Inicia uma CONEXÃO TCP TEMPORÁRIA apenas para o registro.
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                # Monta e envia a mensagem de registro (DeviceInfo).
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                print("--> SUCESSO: Registrado no Gateway.")
                # Fecha a conexão TCP imediatamente, pois o sensor não precisa receber comandos.
                tcp_socket.close() 
                
                # Após o registro, inicia a thread que enviará os dados de status via UDP.
                # Passa o IP descoberto do Gateway como argumento.
                update_thread = threading.Thread(target=send_status_updates, args=(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), discovered_ip), daemon=True)
                update_thread.start()
                # Sai do loop de descoberta.
                break
            except Exception as e:
                # Se falhar, aguarda o próximo anúncio para tentar novamente.
                print(f"Falha ao registrar no Gateway: {e}")
                time.sleep(5)

# Ponto de entrada do script.
if __name__ == "__main__":
    discover_gateway_and_connect()
    # Mantém a thread principal viva para que a thread de envio de status possa rodar.
    while True:
        time.sleep(3600)
