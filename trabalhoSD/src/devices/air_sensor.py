# src/devices/air_sensor.py
import socket
import threading
import time
import uuid
import random
from generated import smart_city_pb2

# --- Configurações ---
# Gera um ID único para este dispositivo.
DEVICE_ID = f"airq_{uuid.uuid4().hex[:6]}"
# Define o tipo do dispositivo a partir do enum do Protocol Buffers.
DEVICE_TYPE = smart_city_pb2.DeviceType.Value('AIR_SENSOR')
# A porta UDP do Gateway para onde os status serão enviados.
GATEWAY_UDP_PORT = 10001
# Constantes para a comunicação multicast de descoberta.
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007

# A função de envio de status agora precisa receber o IP do Gateway, pois ele é descoberto dinamicamente.
def send_status_updates(udp_socket, gateway_ip):
    """
    Envia periodicamente dados de qualidade do ar via UDP para o Gateway.
    
    Esta função roda em uma thread e, a cada 15 segundos, gera um valor
    aleatório e o envia. Este é o comportamento principal de um sensor.
    """
    while True:
        # Simula uma leitura de Partículas Por Milhão (PPM).
        air_quality_ppm = round(random.uniform(30.0, 150.0), 2)
        
        # Constrói a mensagem de status usando Protocol Buffers.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        status = wrapper_msg.status_update
        status.device_id = DEVICE_ID
        status.state_info = f"PPM: {air_quality_ppm}"
        
        # Usa o IP do Gateway (descoberto dinamicamente) para enviar os dados via UDP.
        # UDP é "sem conexão", então cada envio especifica o destino.
        udp_socket.sendto(wrapper_msg.SerializeToString(), (gateway_ip, GATEWAY_UDP_PORT))
        print(f"Enviado status: Qualidade do Ar = {air_quality_ppm:.2f} PPM para {gateway_ip}")
        # Pausa de 15 segundos antes de enviar o próximo status.
        time.sleep(15)

# --- NOVA FUNÇÃO DE DESCOBERTA E CONEXÃO ---
def discover_gateway_and_connect():
    """
    Escuta por anúncios do Gateway na rede para se registrar e, em seguida,
    inicia o envio periódico de status via UDP.
    """
    # Configura um socket para escutar por mensagens multicast na rede.
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.bind(("", MULTICAST_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton("0.0.0.0")
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"Sensor de Qualidade do Ar ({DEVICE_ID}) aguardando anúncio do Gateway...")
    
    # Loop infinito para aguardar o anúncio do Gateway.
    while True:
        # Fica bloqueado aqui até receber uma mensagem multicast.
        data, address = multicast_socket.recvfrom(1024)
        
        # Decodifica a mensagem recebida.
        wrapper_msg = smart_city_pb2.WrapperMessage()
        wrapper_msg.ParseFromString(data)
        
        # Verifica se a mensagem é um anúncio do Gateway.
        if wrapper_msg.HasField("gateway_info"):
            gateway_info = wrapper_msg.gateway_info
            discovered_ip = gateway_info.ip_address
            discovered_port = gateway_info.device_tcp_port
            print(f"--> Gateway encontrado em {discovered_ip}:{discovered_port}. Registrando...")

            try:
                # Inicia uma CONEXÃO TCP TEMPORÁRIA apenas para se registrar.
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((discovered_ip, discovered_port))
                
                # Monta e envia a mensagem de registro (DeviceInfo).
                register_msg = smart_city_pb2.WrapperMessage()
                info = register_msg.device_info
                info.id = DEVICE_ID
                info.type = DEVICE_TYPE
                tcp_socket.send(register_msg.SerializeToString())
                print("--> SUCESSO: Registrado no Gateway.")
                # Fecha a conexão TCP, pois o sensor não precisa receber comandos.
                tcp_socket.close() 
                
                # Após o registro, inicia a thread que enviará os dados de status via UDP.
                # Passa o IP descoberto do Gateway para a função de envio.
                update_thread = threading.Thread(target=send_status_updates, args=(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), discovered_ip), daemon=True)
                update_thread.start()
                # Sai do loop de descoberta, pois o registro foi bem-sucedido.
                break
            except Exception as e:
                # Se o registro falhar, imprime o erro e aguarda o próximo anúncio.
                print(f"Falha ao registrar no Gateway: {e}")
                time.sleep(5)

# Ponto de entrada do script.
if __name__ == "__main__":
    # Inicia o processo de descoberta e conexão.
    discover_gateway_and_connect()
    # Mantém o processo principal vivo para que a thread em daemon possa continuar rodando.
    while True:
        time.sleep(3600)
